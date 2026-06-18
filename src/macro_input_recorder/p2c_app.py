from __future__ import annotations

from datetime import datetime
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from .automation import MacroRunner, RunOptions, StopRequested
from .daily_schedule import daily_run_key, is_due_now, parse_hhmm
from .workflow import MacroWorkflow, ensure_builtin_workflows, load_workflows, workflows_dir


class P2CApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("P2C 포스 자동화")
        self.root.geometry("760x560")
        self.root.minsize(720, 520)
        self.root.configure(bg="#f3f4f6")
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.runner = MacroRunner(self._log)
        self.worker: threading.Thread | None = None
        self.hourly_stop = threading.Event()
        self.schedule_stop = threading.Event()
        self.schedule_thread: threading.Thread | None = None
        self.workflows: list[MacroWorkflow] = []

        self.selected_workflow = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="대기 중")
        self.amount_var = tk.StringVar(value="38500")
        self.count_var = tk.StringVar(value="5")
        self.confidence_var = tk.DoubleVar(value=0.78)
        self.coord_fallback_var = tk.BooleanVar(value=True)
        self.interval_var = tk.StringVar(value="60")
        self.open_time_var = tk.StringVar(value="10:30")
        self.close_time_var = tk.StringVar(value="21:30")
        self.schedule_status_var = tk.StringVar(value="예약 대기")
        self.schedule_autostart_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._reload_workflows()
        self._poll_log()
        if self.schedule_autostart_var.get():
            self.start_daily_schedule(quiet=True)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(outer, text="P2C 포스 자동화", font=("Malgun Gothic", 18, "bold"))
        title.pack(anchor=tk.W)

        notebook = ttk.Notebook(outer)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.run_tab = ttk.Frame(notebook, padding=12)
        self.settings_tab = ttk.Frame(notebook, padding=12)
        self.log_tab = ttk.Frame(notebook, padding=12)
        notebook.add(self.run_tab, text="실행")
        notebook.add(self.settings_tab, text="설정")
        notebook.add(self.log_tab, text="로그")
        self._build_run_tab()
        self._build_settings_tab()
        self._build_log_tab()

    def _build_run_tab(self) -> None:
        self.run_tab.columnconfigure(0, weight=1)
        self.run_tab.rowconfigure(0, weight=1)

        button_frame = ttk.Frame(self.run_tab)
        button_frame.grid(row=0, column=0, sticky="nsew")
        for column in range(3):
            button_frame.columnconfigure(column, weight=1, uniform="actions")
        button_frame.rowconfigure(0, weight=1)

        actions = [
            ("가승인", "#16a34a", "#ffffff", "가승인"),
            ("개점", "#2563eb", "#ffffff", "개점"),
            ("마감", "#dc2626", "#ffffff", "마감"),
        ]
        for column, (text, bg, fg, workflow_name) in enumerate(actions):
            button = tk.Button(
                button_frame,
                text=text,
                command=lambda name=workflow_name: self.run_named_once(name),
                bg=bg,
                fg=fg,
                activebackground=bg,
                activeforeground=fg,
                relief=tk.FLAT,
                font=("Malgun Gothic", 30, "bold"),
                cursor="hand2",
                bd=0,
                highlightthickness=0,
            )
            button.grid(row=0, column=column, sticky="nsew", padx=10, pady=16)

    def _build_settings_tab(self) -> None:
        status = ttk.Frame(self.settings_tab)
        status.pack(fill=tk.X)
        ttk.Label(status, text="상태").pack(side=tk.LEFT)
        ttk.Label(status, textvariable=self.status_var, font=("Malgun Gothic", 11, "bold")).pack(side=tk.LEFT, padx=(8, 0))

        row = ttk.Frame(self.settings_tab)
        row.pack(fill=tk.X, pady=(14, 0))
        ttk.Label(row, text="내장 작업 선택").pack(side=tk.LEFT)
        self.workflow_combo = ttk.Combobox(row, textvariable=self.selected_workflow, state="readonly", width=42)
        self.workflow_combo.pack(side=tk.LEFT, padx=(8, 8))
        ttk.Button(row, text="내장 작업 복구", command=lambda: self._reload_workflows(force_builtin=True)).pack(side=tk.LEFT)

        settings = ttk.LabelFrame(self.settings_tab, text="기본 설정", padding=10)
        settings.pack(fill=tk.X, pady=(14, 0))
        ttk.Label(settings, text="가승인 금액").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(settings, textvariable=self.amount_var, width=12).grid(row=0, column=1, sticky=tk.W, padx=(8, 18))
        ttk.Label(settings, text="시간당 싸이버거 세트 수량").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(settings, textvariable=self.count_var, width=8).grid(row=0, column=3, sticky=tk.W, padx=(8, 18))
        ttk.Label(settings, text="이미지 인식 기준").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        ttk.Scale(settings, variable=self.confidence_var, from_=0.60, to=0.95, orient=tk.HORIZONTAL, length=180).grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=(8, 18), pady=(8, 0))
        ttk.Checkbutton(settings, text="이미지 인식 실패 시 좌표 보정 사용", variable=self.coord_fallback_var).grid(row=1, column=3, columnspan=2, sticky=tk.W, pady=(8, 0))

        buttons = ttk.LabelFrame(self.settings_tab, text="수동 실행", padding=10)
        buttons.pack(fill=tk.X, pady=(14, 0))
        ttk.Button(buttons, text="선택 작업 1회 실행", command=self.run_selected_once).pack(side=tk.LEFT)
        ttk.Button(buttons, text="중지", command=self.stop_all).pack(side=tk.LEFT, padx=(8, 0))

        daily = ttk.LabelFrame(self.settings_tab, text="일일 예약 실행", padding=10)
        daily.pack(fill=tk.X, pady=(14, 0))
        ttk.Label(daily, text="개점").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(daily, textvariable=self.open_time_var, width=8).grid(row=0, column=1, sticky=tk.W, padx=(6, 14))
        ttk.Label(daily, text="마감").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(daily, textvariable=self.close_time_var, width=8).grid(row=0, column=3, sticky=tk.W, padx=(6, 14))
        ttk.Button(daily, text="예약 시작", command=self.start_daily_schedule).grid(row=0, column=4, sticky=tk.W)
        ttk.Button(daily, text="예약 중지", command=self.stop_daily_schedule).grid(row=0, column=5, sticky=tk.W, padx=(8, 0))
        ttk.Checkbutton(daily, text="프로그램 실행 시 자동 시작", variable=self.schedule_autostart_var).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(8, 0))
        ttk.Label(daily, textvariable=self.schedule_status_var, font=("Malgun Gothic", 10, "bold")).grid(row=1, column=3, columnspan=3, sticky=tk.W, pady=(8, 0))

        hourly = ttk.LabelFrame(self.settings_tab, text="시간당 가승인", padding=10)
        hourly.pack(fill=tk.X, pady=(14, 0))
        ttk.Label(hourly, text="간격(분)").pack(side=tk.LEFT)
        ttk.Entry(hourly, textvariable=self.interval_var, width=8).pack(side=tk.LEFT, padx=(8, 8))
        ttk.Button(hourly, text="시간당 자동 시작", command=self.start_hourly).pack(side=tk.LEFT)
        ttk.Button(hourly, text="자동 중지", command=self.stop_all).pack(side=tk.LEFT, padx=(8, 0))

    def _build_log_tab(self) -> None:
        self.log_text = tk.Text(self.log_tab, height=20, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _reload_workflows(self, select: str | None = None, force_builtin: bool = False) -> None:
        try:
            ensure_builtin_workflows(force=force_builtin)
        except Exception as exc:
            self._log(f"내장 작업 준비 오류: {exc}")
        self.workflows = load_workflows()
        values = [w.name for w in self.workflows]
        self.workflow_combo.configure(values=values)
        if select and select in values:
            self.selected_workflow.set(select)
        elif values and self.selected_workflow.get() not in values:
            self.selected_workflow.set(values[0])
        elif not values:
            self.selected_workflow.set("")

    def selected(self) -> MacroWorkflow | None:
        name = self.selected_workflow.get()
        for workflow in self.workflows:
            if workflow.name == name:
                return workflow
        return None

    def find_workflow(self, label: str) -> MacroWorkflow | None:
        normalized = label.strip()
        for workflow in self.workflows:
            if workflow.name == normalized:
                return workflow
        for workflow in self.workflows:
            if workflow.name.startswith(normalized):
                return workflow
        for workflow in self.workflows:
            if normalized in workflow.name:
                return workflow
        return None

    def options(self) -> RunOptions:
        return RunOptions(confidence=float(self.confidence_var.get()), coordinate_fallback=bool(self.coord_fallback_var.get()))

    def run_selected_once(self) -> None:
        workflow = self.selected()
        if workflow is None:
            messagebox.showwarning("작업 없음", "내장 작업을 불러오지 못했습니다. 프로그램을 다시 실행해 주세요.")
            return
        self._start_workflow(workflow)

    def run_named_once(self, label: str) -> None:
        workflow = self.find_workflow(label)
        if workflow is None:
            messagebox.showwarning("작업 없음", f"내장 '{label}' 작업을 불러오지 못했습니다. 프로그램을 다시 실행해 주세요.")
            return
        self.selected_workflow.set(workflow.name)
        self._start_workflow(workflow)

    def _start_workflow(self, workflow: MacroWorkflow) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("실행 중", "이미 작업이 실행 중입니다.")
            return
        self._hide_control_window()
        self.worker = threading.Thread(target=self._run_worker, args=(workflow,), daemon=True)
        self.worker.start()

    def _start_scheduled_named(self, label: str) -> None:
        if self.worker and self.worker.is_alive():
            self._log(f"예약 {label} 건너뜀: 다른 작업 실행 중")
            return
        workflow = self.find_workflow(label)
        if workflow is None:
            self._log(f"예약 {label} 실패: 내장 작업 없음")
            return
        self._hide_control_window()
        self.worker = threading.Thread(target=self._run_worker, args=(workflow, False), daemon=True)
        self.worker.start()

    def _run_worker(self, workflow: MacroWorkflow, restore_window: bool = True) -> None:
        self.status_var.set(f"실행 중: {workflow.name}")
        try:
            self.runner.run(workflow, self.options())
            self.status_var.set("완료")
        except StopRequested as exc:
            self._log(str(exc))
            self.status_var.set("중지됨")
        except Exception as exc:
            self._log(f"오류: {exc}")
            self.status_var.set(f"오류: {exc}")
        finally:
            if restore_window:
                self.root.after(0, self._show_control_window)

    def start_daily_schedule(self, quiet: bool = False) -> None:
        if self.schedule_thread and self.schedule_thread.is_alive():
            if not quiet:
                messagebox.showinfo("예약 실행", "이미 예약 실행이 켜져 있습니다.")
            return
        try:
            open_time = parse_hhmm(self.open_time_var.get())
            close_time = parse_hhmm(self.close_time_var.get())
        except Exception as exc:
            self.schedule_status_var.set("예약 시간 오류")
            if not quiet:
                messagebox.showerror("예약 시간 오류", str(exc))
            return
        self.schedule_stop.clear()
        self.schedule_thread = threading.Thread(target=self._daily_schedule_worker, args=(open_time, close_time), daemon=True)
        self.schedule_thread.start()
        self.schedule_status_var.set(f"예약 실행 중: 개점 {self.open_time_var.get()} / 마감 {self.close_time_var.get()}")
        self._log(f"일일 예약 시작: 개점 {self.open_time_var.get()} / 마감 {self.close_time_var.get()}")

    def stop_daily_schedule(self) -> None:
        self.schedule_stop.set()
        self.schedule_status_var.set("예약 중지됨")
        self._log("일일 예약 중지")

    def _daily_schedule_worker(self, open_time: tuple[int, int], close_time: tuple[int, int]) -> None:
        last_open_key: str | None = None
        last_close_key: str | None = None
        while not self.schedule_stop.is_set():
            now = datetime.now()
            if is_due_now(now, open_time, last_open_key):
                last_open_key = daily_run_key(now)
                self._log(f"{now.strftime('%H:%M')} 예약 개점 실행")
                self.root.after(0, lambda: self._start_scheduled_named("개점"))
            if is_due_now(now, close_time, last_close_key):
                last_close_key = daily_run_key(now)
                self._log(f"{now.strftime('%H:%M')} 예약 마감 실행")
                self.root.after(0, lambda: self._start_scheduled_named("마감"))
            self.schedule_stop.wait(5)

    def start_hourly(self) -> None:
        workflow = self.selected()
        if workflow is None:
            messagebox.showwarning("작업 없음", "가승인 내장 작업을 선택해주세요.")
            return
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("실행 중", "이미 작업이 실행 중입니다.")
            return
        self.hourly_stop.clear()
        self._hide_control_window()
        self.worker = threading.Thread(target=self._hourly_worker, args=(workflow,), daemon=True)
        self.worker.start()

    def _hourly_worker(self, workflow: MacroWorkflow) -> None:
        try:
            interval = max(1, int(self.interval_var.get())) * 60
        except ValueError:
            interval = 3600
        self.status_var.set("시간당 자동 실행 중")
        while not self.hourly_stop.is_set():
            started = time.strftime("%H:%M:%S")
            self._log(f"{started} 가승인 자동 실행: {self.count_var.get()}개 / {self.amount_var.get()}원")
            try:
                self.runner.run(workflow, self.options())
            except StopRequested:
                break
            except Exception as exc:
                self._log(f"자동 실행 오류: {exc}")
            if self.hourly_stop.wait(interval):
                break
        self.status_var.set("자동 실행 중지됨")
        self.root.after(0, self._show_control_window)

    def _hide_control_window(self) -> None:
        try:
            self.root.iconify()
        except Exception:
            pass

    def _show_control_window(self) -> None:
        try:
            self.root.deiconify()
        except Exception:
            pass

    def stop_all(self) -> None:
        self.hourly_stop.set()
        self.runner.stop()
        self.status_var.set("중지 요청됨")

    def open_workflow_folder(self) -> None:
        import os
        import platform
        import subprocess

        path = workflows_dir()
        if platform.system() == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)

    def _log(self, message: str) -> None:
        self.log_queue.put(f"{time.strftime('%H:%M:%S')}  {message}")

    def _poll_log(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.insert(tk.END, line + "\n")
            self.log_text.see(tk.END)
        self.root.after(200, self._poll_log)


def main() -> int:
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    P2CApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
