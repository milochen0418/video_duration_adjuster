import reflex as rx
from video_duration_adjuster.states.video_state import VideoState


def input_field(
    label: str, value_var: rx.Var, on_change: rx.event.EventType
) -> rx.Component:
    return rx.el.div(
        rx.el.label(label, class_name="text-xs text-gray-600 font-bold mb-1 ml-1"),
        rx.el.input(
            type="number",
            placeholder="0",
            default_value=value_var,
            on_change=on_change.debounce(300),
            class_name="w-full bg-white border border-gray-300 rounded-xl px-4 py-3 text-gray-900 focus:border-violet-500 focus:ring-1 focus:ring-violet-500 outline-none transition-all",
        ),
        class_name="flex flex-col flex-1",
    )


def speed_indicator() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.match(
                VideoState.speed_ratio,
                (1.0, rx.icon("equal", class_name="h-6 w-6 text-blue-400")),
            ),
            rx.cond(
                VideoState.speed_ratio > 1.0,
                rx.icon("fast-forward", class_name="h-6 w-6 text-green-400"),
                rx.cond(
                    VideoState.speed_ratio < 1.0,
                    rx.icon("rewind", class_name="h-6 w-6 text-orange-400"),
                    None,
                ),
            ),
            class_name="p-3 rounded-2xl bg-gray-50 border border-gray-200",
        ),
        rx.el.div(
            rx.el.p(
                "Playback Speed", class_name="text-xs text-gray-600 font-bold uppercase"
            ),
            rx.el.p(
                VideoState.speed_description, class_name="text-xl font-black text-gray-900"
            ),
            class_name="flex flex-col ml-4",
        ),
        class_name="flex items-center p-6 bg-white rounded-3xl border border-gray-200",
    )


def time_controls() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.h3("Target Duration", class_name="text-xl font-bold text-gray-900"),
                rx.el.div(
                    rx.el.button(
                        "Time Format",
                        on_click=lambda: VideoState.set_input_mode("time"),
                        class_name=rx.cond(
                            VideoState.input_mode == "time",
                            "px-4 py-1.5 rounded-lg bg-violet-600 text-white text-xs font-bold transition-all",
                            "px-4 py-1.5 rounded-lg bg-gray-100 text-gray-600 text-xs font-bold hover:bg-gray-200 transition-all",
                        ),
                    ),
                    rx.el.button(
                        "Total Seconds",
                        on_click=lambda: VideoState.set_input_mode("seconds"),
                        class_name=rx.cond(
                            VideoState.input_mode == "seconds",
                            "px-4 py-1.5 rounded-lg bg-violet-600 text-white text-xs font-bold transition-all",
                            "px-4 py-1.5 rounded-lg bg-gray-100 text-gray-600 text-xs font-bold hover:bg-gray-200 transition-all",
                        ),
                    ),
                    class_name="flex gap-2 p-1 bg-gray-50 rounded-xl border border-gray-200",
                ),
                class_name="flex justify-between items-center mb-6",
            ),
            rx.cond(
                VideoState.input_mode == "time",
                rx.el.div(
                    input_field(
                        "Hours", VideoState.target_hours, VideoState.update_target_hours
                    ),
                    input_field(
                        "Minutes",
                        VideoState.target_minutes,
                        VideoState.update_target_minutes,
                    ),
                    input_field(
                        "Seconds",
                        VideoState.target_seconds,
                        VideoState.update_target_seconds,
                    ),
                    class_name="flex flex-col md:flex-row gap-4",
                ),
                rx.el.div(
                    input_field(
                        "Total Seconds",
                        VideoState.target_total_seconds,
                        VideoState.update_target_total_seconds,
                    )
                ),
            ),
            class_name="mb-8",
        ),
        speed_indicator(),
        rx.cond(
            VideoState.speed_warning != "",
            rx.el.div(
                rx.icon("git_pull_request_create", class_name="h-4 w-4 mr-2 shrink-0"),
                rx.el.p(VideoState.speed_warning, class_name="text-sm"),
                class_name="mt-4 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-500 flex items-center",
            ),
        ),
        rx.el.div(
            rx.el.div(
                rx.icon("info", class_name="h-5 w-5 text-violet-400 mr-3"),
                rx.el.p(
                    "We use high-quality audio time-stretching to ensure voices don't sound like chipmunks when speeding up.",
                    class_name="text-sm text-gray-600",
                ),
                class_name="flex items-start p-6 bg-violet-500/5 rounded-3xl border border-violet-500/10 mt-8 mb-8",
            ),
            rx.el.div(
                rx.el.button(
                    rx.cond(
                        VideoState.is_processing,
                        rx.el.span(
                            rx.icon("loader-circle", class_name="h-4 w-4 mr-2 animate-spin"),
                            "Processing...",
                            class_name="flex items-center justify-center",
                        ),
                        "Generate Preview (5s)",
                    ),
                    on_click=VideoState.generate_preview,
                    disabled=~VideoState.is_input_valid | VideoState.is_processing,
                    class_name=rx.cond(
                        VideoState.is_input_valid & ~VideoState.is_processing,
                        "flex-1 py-4 rounded-2xl bg-gray-900 text-white font-bold text-sm border border-gray-900 hover:bg-gray-800 transition-all cursor-pointer",
                        "flex-1 py-4 rounded-2xl bg-gray-100 text-gray-500 font-bold text-sm border border-gray-200 cursor-not-allowed",
                    ),
                ),
                rx.el.button(
                    rx.cond(
                        VideoState.is_processing,
                        rx.el.span(
                            rx.icon("loader-circle", class_name="h-4 w-4 mr-2 animate-spin"),
                            "Processing...",
                            class_name="flex items-center justify-center",
                        ),
                        "Process Full Video",
                    ),
                    on_click=VideoState.process_video,
                    disabled=~VideoState.is_input_valid | VideoState.is_processing,
                    class_name=rx.cond(
                        VideoState.is_input_valid & ~VideoState.is_processing,
                        "flex-1 py-4 rounded-2xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-bold text-sm shadow-xl shadow-violet-600/20 hover:scale-[1.02] active:scale-[0.98] transition-all cursor-pointer",
                        "flex-1 py-4 rounded-2xl bg-gray-100 text-gray-500 font-bold text-sm border border-gray-200 cursor-not-allowed",
                    ),
                ),
                class_name="flex gap-4 w-full",
            ),
            rx.cond(
                VideoState.is_processing,
                rx.el.div(
                    rx.el.div(
                        rx.el.div(
                            class_name="h-full bg-violet-500 rounded-full transition-all duration-300 relative overflow-hidden",
                            style={"width": f"{VideoState.processing_progress}%"},
                        ),
                        class_name="h-2 w-full bg-gray-200 rounded-full overflow-hidden mb-3",
                    ),
                    rx.el.div(
                        rx.el.span(
                            VideoState.processing_status,
                            class_name="text-sm text-gray-700 font-medium",
                        ),
                        rx.el.span(
                            f"{VideoState.processing_progress}%",
                            class_name="text-sm text-violet-400 font-bold",
                        ),
                        class_name="flex justify-between items-center",
                    ),
                    class_name="mt-8 animate-in fade-in slide-in-from-top-4 duration-500",
                ),
            ),
            rx.cond(
                VideoState.error_message != "",
                rx.el.div(
                    rx.icon("wheat", class_name="h-5 w-5 text-red-400 mr-2"),
                    rx.el.p(
                        VideoState.error_message, class_name="text-sm text-red-400"
                    ),
                    class_name="mt-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center",
                ),
            ),
        ),
        class_name="w-full p-8 rounded-[2.5rem] bg-white border border-gray-200 h-fit shadow-sm",
    )