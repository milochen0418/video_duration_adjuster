import reflex as rx
from video_duration_adjuster.states.video_state import VideoState
from video_duration_adjuster.components.navbar import navbar
from video_duration_adjuster.components.upload_zone import upload_zone
from video_duration_adjuster.components.video_preview import video_info_card


def index() -> rx.Component:
    return rx.el.main(
        navbar(),
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.h1(
                        "Manipulate Time in Seconds.",
                        class_name="text-4xl md:text-6xl font-black text-white text-center mb-6 tracking-tight leading-tight",
                    ),
                    rx.el.p(
                        "Change the duration of your videos without losing quality. We preserve audio pitch automatically using professional algorithms.",
                        class_name="text-lg md:text-xl text-gray-400 text-center max-w-2xl mx-auto mb-16 font-medium",
                    ),
                    class_name="pt-12 md:pt-20",
                ),
                rx.el.div(
                    rx.cond(VideoState.is_uploaded, video_info_card(), upload_zone()),
                    class_name="flex justify-center",
                ),
                class_name="max-w-6xl mx-auto px-6 pb-24",
            ),
            class_name="flex-1",
        ),
        rx.el.div(
            class_name="fixed -bottom-[20vh] -left-[10vw] w-[50vw] h-[50vh] bg-violet-600/10 blur-[120px] rounded-full -z-10"
        ),
        rx.el.div(
            class_name="fixed -top-[10vh] -right-[10vw] w-[40vw] h-[40vh] bg-fuchsia-600/10 blur-[100px] rounded-full -z-10"
        ),
        class_name="min-h-screen bg-gray-950 font-['Inter'] relative overflow-x-hidden",
    )


app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(rel="preconnect", href="https://fonts.gstatic.com", cross_origin=""),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(index, route="/")