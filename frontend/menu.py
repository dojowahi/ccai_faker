from nicegui import ui


def menu() -> None:
    ui.link('Home', '/').classes(replace='text-black')
    ui.link('Generate CCAI Logs', '/ccai-datagen/').classes(replace='text-black')
    ui.link('Check Status', '/ccai-status/').classes(replace='text-black')