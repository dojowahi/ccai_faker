from nicegui import ui
from pages.ccai_datagen import ccai_datagen
from pages.ccai_status import ccai_status

def create() -> None:
    ui.page('/ccai-datagen/')(ccai_datagen)
    ui.page('/ccai-status/')(ccai_status)

if __name__ == '__main__':
    create()