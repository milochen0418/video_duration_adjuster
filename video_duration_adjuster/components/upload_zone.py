import reflex as rx
from video_duration_adjuster.states.video_state import VideoState


def upload_zone() -> rx.Component:
    return rx.upload.root(
        rx.el.div(
            rx.el.div(
                rx.cond(
                    VideoState.is_uploading,
                    rx.el.div(
                        rx.icon(
                            "squirrel",
                            class_name="h-12 w-12 text-violet-500 animate-spin mb-4",
                        ),
                        rx.el.p(
                            "Processing Video...",
                            class_name="text-xl font-semibold text-gray-900",
                        ),
                        rx.el.p(
                            "Hang tight, we're analyzing your file",
                            class_name="text-gray-600 mt-2",
                        ),
                        class_name="flex flex-col items-center",
                    ),
                    rx.el.div(
                        rx.el.div(
                            rx.icon(
                                "pen",
                                class_name="h-12 w-12 text-violet-400 group-hover:scale-110 transition-transform duration-300",
                            ),
                            class_name="p-4 rounded-full bg-violet-500/10 mb-4 group-hover:bg-violet-500/20 transition-colors",
                        ),
                        rx.el.h3(
                            "Upload your video",
                            class_name="text-xl font-bold text-gray-900 mb-2",
                        ),
                        rx.el.p(
                            "Drag and drop or click to browse",
                            class_name="text-gray-600 text-center mb-6",
                        ),
                        rx.el.div(
                            rx.el.span(
                                "MP4",
                                class_name="px-3 py-1 rounded-md bg-gray-100 text-gray-600 text-xs font-bold border border-gray-200",
                            ),
                            rx.el.span(
                                "MOV",
                                class_name="px-3 py-1 rounded-md bg-gray-100 text-gray-600 text-xs font-bold border border-gray-200",
                            ),
                            rx.el.span(
                                "WEBM",
                                class_name="px-3 py-1 rounded-md bg-gray-100 text-gray-600 text-xs font-bold border border-gray-200",
                            ),
                            class_name="flex gap-2 justify-center",
                        ),
                        class_name="flex flex-col items-center",
                    ),
                ),
                class_name="group w-full max-w-xl p-12 border-2 border-dashed border-gray-300 hover:border-violet-500/50 rounded-3xl bg-white hover:bg-gray-50 transition-all cursor-pointer flex flex-col items-center justify-center animate-in fade-in zoom-in duration-500 shadow-sm",
            )
        ),
        id="video_upload",
        multiple=False,
        accept={"video/*": [".mp4", ".mov", ".webm"]},
        on_drop=VideoState.handle_upload(rx.upload_files(upload_id="video_upload")),
        class_name="w-full flex justify-center",
    )