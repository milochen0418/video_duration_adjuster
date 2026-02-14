import reflex as rx
from video_duration_adjuster.states.video_state import VideoState


def stat_item(icon_name: str, label: str, value: str) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon(icon_name, class_name="h-5 w-5 text-violet-400"),
            class_name="p-2 rounded-lg bg-violet-500/10 mr-3 shrink-0",
        ),
        rx.el.div(
            rx.el.p(
                label,
                class_name="text-xs text-gray-500 font-bold uppercase tracking-wider",
            ),
            rx.el.p(
                value,
                class_name="text-base md:text-lg font-semibold text-gray-900 leading-tight break-words",
            ),
            class_name="flex flex-col min-w-0",
        ),
        class_name="flex items-center p-4 bg-white rounded-2xl border border-gray-200 min-w-0",
    )


from video_duration_adjuster.components.time_controls import time_controls


def step_badge(step: str, title: str) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            step,
            class_name="inline-flex items-center justify-center h-6 min-w-6 px-2 rounded-full bg-violet-100 text-violet-700 text-xs font-black",
        ),
        rx.el.h3(title, class_name="text-lg font-bold text-gray-900"),
        class_name="flex items-center gap-3 mb-4",
    )


def result_preview(title: str, file_path: str, is_ready: bool) -> rx.Component:
    return rx.cond(
        is_ready,
        rx.el.div(
            rx.el.h3(title, class_name="text-lg font-bold text-gray-900 mb-4"),
            rx.el.video(
                src=rx.get_upload_url(file_path),
                controls=True,
                class_name="w-full h-auto aspect-video rounded-xl shadow-lg border border-gray-200 bg-black mb-4",
            ),
            rx.el.a(
                rx.el.button(
                    rx.icon("download", class_name="h-4 w-4 mr-2"),
                    "Download Video",
                    class_name="w-full py-3 rounded-xl bg-gray-900 text-white text-sm font-bold border border-gray-900 hover:bg-gray-800 transition-all flex items-center justify-center",
                ),
                href=rx.get_upload_url(file_path),
                download=file_path,
                class_name="w-full",
            ),
            class_name="animate-in fade-in zoom-in duration-500 p-6 bg-white rounded-2xl border border-gray-200",
        ),
    )


def video_info_card() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    step_badge("STEP 1", "Original Video"),
                    rx.el.video(
                        src=rx.get_upload_url(VideoState.uploaded_file),
                        controls=True,
                        class_name="w-full h-auto aspect-video rounded-2xl shadow-2xl border border-gray-200 bg-black",
                    ),
                    class_name="mb-8 overflow-hidden p-6 bg-white rounded-2xl border border-gray-200",
                ),
                rx.el.div(
                    step_badge("STEP 2", "Video Information"),
                    rx.el.h2(
                        VideoState.file_name,
                        class_name="text-2xl font-bold text-gray-900 truncate mb-2",
                    ),
                    rx.el.p(
                        "Video analysis complete. Ready for time adjustment.",
                        class_name="text-gray-600 text-sm mb-6",
                    ),
                    rx.el.div(
                        stat_item("clock", "Duration", VideoState.duration_formatted),
                        stat_item(
                            "maximize",
                            "Resolution",
                            f"{VideoState.width}x{VideoState.height}",
                        ),
                        stat_item("database", "Size", f"{VideoState.file_size_mb} MB"),
                        class_name="grid grid-cols-1 md:grid-cols-3 gap-4",
                    ),
                    class_name="mb-8 p-6 bg-white rounded-2xl border border-gray-200",
                ),
                rx.el.div(
                    step_badge("STEP 3", "Set Target Duration"),
                    time_controls(),
                    class_name="mb-8 p-6 bg-white rounded-2xl border border-gray-200",
                ),
                rx.cond(
                    VideoState.preview_ready,
                    rx.el.div(
                        step_badge("STEP 4", "Preview Result"),
                        result_preview(
                            "Preview (5s)",
                            VideoState.preview_file,
                            VideoState.preview_ready,
                        ),
                        class_name="mb-8 p-6 bg-white rounded-2xl border border-gray-200",
                    ),
                ),
                rx.cond(
                    VideoState.is_processed,
                    rx.el.div(
                        step_badge("STEP 5", "Final Output"),
                        result_preview(
                            "Final Processed Video",
                            VideoState.processed_file,
                            VideoState.is_processed,
                        ),
                        class_name="mb-8 p-6 bg-white rounded-2xl border border-gray-200",
                    ),
                ),
                rx.el.div(
                    rx.el.button(
                        rx.icon("refresh-ccw", class_name="h-4 w-4 mr-2"),
                        "Upload Different Video",
                        on_click=VideoState.reset_upload,
                        class_name="px-6 py-3 rounded-xl bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 hover:text-gray-900 transition-all flex items-center font-medium",
                    ),
                    class_name="flex flex-wrap items-center justify-start gap-4 pt-6 border-t border-gray-200",
                ),
                class_name="w-full p-8 rounded-[2.5rem] bg-gray-50/90 backdrop-blur-xl border border-gray-200 shadow-2xl",
            ),
            class_name="w-full max-w-4xl",
        ),
        class_name="w-full flex justify-center animate-in slide-in-from-bottom-8 duration-700",
    )