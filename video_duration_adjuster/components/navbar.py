import reflex as rx


def step_item(step: str, title: str, description: str) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                step,
                class_name="inline-flex items-center justify-center h-6 min-w-6 px-2 rounded-full bg-violet-100 text-violet-700 text-xs font-black",
            ),
            rx.el.p(title, class_name="text-sm font-bold text-gray-900"),
            class_name="flex items-center gap-3 mb-1",
        ),
        rx.el.p(description, class_name="text-sm text-gray-600 leading-relaxed"),
        class_name="p-4 rounded-xl border border-gray-200 bg-white",
    )


def documentation_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.el.button(
                "Documentation",
                class_name="text-gray-600 hover:text-gray-900 transition-colors text-sm font-medium",
            )
        ),
        rx.dialog.content(
            rx.dialog.title("How This App Works", class_name="text-lg font-bold"),
            rx.dialog.description(
                "This app processes your video in 5 steps:",
                class_name="text-sm text-gray-600 mb-4",
            ),
            rx.el.div(
                step_item("STEP 1", "Original Video", "Upload a video file and preview the source clip."),
                step_item("STEP 2", "Video Information", "Read duration, resolution, and file size from video metadata."),
                step_item("STEP 3", "Set Target Duration", "Set target duration by time format or total seconds to calculate playback speed."),
                step_item("STEP 4", "Preview Result", "Generate a short preview to quickly check pacing and audio quality."),
                step_item("STEP 5", "Final Output", "Process and download the full adjusted video."),
                class_name="space-y-3 max-h-[55vh] overflow-y-auto pr-1",
            ),
            rx.el.div(
                rx.dialog.close(
                    rx.el.button(
                        "Close",
                        class_name="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-800 transition-all",
                    )
                ),
                class_name="mt-6 flex justify-end",
            ),
            class_name="max-w-2xl",
        ),
    )


def navbar() -> rx.Component:
    return rx.el.nav(
        rx.el.div(
            rx.el.div(
                rx.icon("video", class_name="h-8 w-8 text-violet-500"),
                rx.el.span(
                    "TimeShift",
                    class_name="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-violet-500 to-fuchsia-600",
                ),
                class_name="flex items-center gap-2",
            ),
            rx.el.div(
                documentation_dialog(),
                rx.el.a(
                    rx.el.button(
                        "Github",
                        class_name="px-4 py-2 rounded-lg bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 transition-all text-sm font-medium",
                    ),
                    href="https://github.com/milochen0418/video_duration_adjuster",
                    target="_blank",
                    rel="noopener noreferrer",
                ),
                class_name="flex items-center gap-6",
            ),
            class_name="max-w-6xl mx-auto flex justify-between items-center px-6 h-20",
        ),
        class_name="w-full border-b border-gray-200 bg-white/95 backdrop-blur-md fixed top-0 left-0 z-[1000]",
    )