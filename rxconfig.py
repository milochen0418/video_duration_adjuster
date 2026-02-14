import reflex as rx

config = rx.Config(
    app_name="video_duration_adjuster",
    api_url="http://localhost:8000",
    plugins=[
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.SitemapPlugin(),
    ],
)
