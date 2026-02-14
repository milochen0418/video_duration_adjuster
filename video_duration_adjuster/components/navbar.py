import reflex as rx


def navbar() -> rx.Component:
    return rx.el.nav(
        rx.el.div(
            rx.el.div(
                rx.icon("video", class_name="h-8 w-8 text-violet-500"),
                rx.el.span(
                    "TimeShift",
                    class_name="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-violet-400 to-fuchsia-500",
                ),
                class_name="flex items-center gap-2",
            ),
            rx.el.div(
                rx.el.a(
                    "Documentation",
                    href="#",
                    class_name="text-gray-600 hover:text-gray-900 transition-colors text-sm font-medium",
                ),
                rx.el.a(
                    rx.el.button(
                        "Github",
                        class_name="px-4 py-2 rounded-lg bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 transition-all text-sm font-medium",
                    ),
                    href="https://github.com",
                ),
                class_name="flex items-center gap-6",
            ),
            class_name="max-w-6xl mx-auto flex justify-between items-center px-6 h-20",
        ),
        class_name="w-full border-b border-gray-200 bg-white/95 backdrop-blur-md fixed top-0 left-0 z-[1000]",
    )