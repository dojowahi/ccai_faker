import uuid
import json
from google.cloud import pubsub_v1
from nicegui import ui
import theme
from dotenv import load_dotenv
import logging 
import os
import datetime
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# Uses values from .env, good for local testing
# project_id = os.getenv("PROJECT_ID")
# topic_id = os.getenv("START_TOPIC_ID")

# Use value from github action
project_id = os.environ.get('PROJECT_ID')
topic_id = os.environ.get('START_TOPIC_ID')
# Initialize Pub/Sub


publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(project_id, topic_id)


def publish_to_pubsub(message):
    message_data = json.dumps(message).encode("utf-8")
    future = publisher.publish(topic_path, message_data)
    future.result()


ui.add_head_html('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap">')  # Import Roboto font
ui.add_head_html('''
<style>
body {
    font-family: 'Roboto', sans-serif;
    background-color: #f5f5f5; 
}
.container {
    max-width: 600px;
    margin: 20px auto;
    padding: 20px;
    background-color: #fff;
    border-radius:   
 8px;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);   

}
.q-field__label {
    font-weight: 500;
}
.container .q-field input { 
    width: 100%; 
    overflow-x: auto; 
}
</style>
''')

# Main function to create the UI for the CCAI Synthetic Call Generator
def ccai_datagen():
    with theme.frame('CCAI Synthetic Call Generator'):
# with ui.column().classes('container'):
        # ui.label('CCAI Synthetic Call Generator').classes('text-h4 q-mb-md')

        company_name_input = ui.input(label='Company Name', value='Ulta Beauty').props('rounded outlined dense').classes('q-mb-sm ')
        company_website_input = ui.input(label='Company Website', value='https://www.ulta.com/').props('size=50 rounded outlined dense').classes('q-mb-sm ')
        company_reviews_input = ui.input(label='Company Reviews', value='https://www.trustpilot.com/review/www.ulta.com').props("size=80 rounded outlined dense").classes('q-mb-sm')

        # with ui.row().classes('items-center q-mb-sm'):  # Align number input and buttons in a row
        num_log_files_input = ui.number(label='Number of log files', value=1, min=1, max=10001, precision=0,step=1).props('rounded outlined dense').style('width: 150px').classes('q-mb-sm')
        
        with ui.input('Log Start Date') as start_date:
            with ui.menu().props('no-parent-event') as menu:
                with ui.date().bind_value(start_date):
                    with ui.row().classes('justify-end'):
                        ui.button('Close', on_click=menu.close).props('flat')
            with start_date.add_slot('append'):
                ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')

        with ui.input('Log End Date') as end_date:
            with ui.menu().props('no-parent-event') as menu:
                with ui.date().bind_value(end_date):
                    with ui.row().classes('justify-end'):
                        ui.button('Close', on_click=menu.close).props('flat')
            with end_date.add_slot('append'):
                ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')


        ui.label('Temperature')
        temperature_slider = ui.slider(min=0, max=1, step=0.1, value=0.5).props('label-always') \
        .on('update:model-value', lambda e: ui.notify(e.args),
            throttle=1.0)
        

        # ui.input(label='[OPTIONAL] GCS bucket in your org').props("size=40").classes('q-mb-sm')

        output_label = ui.label()

        def submit():
            group_id = str(uuid.uuid4())
            
            

            message = {
                "group_id": group_id,
                "company_name": company_name_input.value,
                "company_website": company_website_input.value,
                "company_reviews": company_reviews_input.value,
                "temperature": temperature_slider.value,
                "num_log_files": int(num_log_files_input.value),
                "start_date": start_date.value,
                "end_date": end_date.value
            }
            print(f"Log files:{num_log_files_input.value}, Company_Name:{company_name_input.value}, GroupId:{group_id}, StartDate:{start_date.value}")


            publish_to_pubsub(message)
            

            output_label.text = f"Submitted {num_log_files_input.value} tasks with Group ID: {group_id}"


        ui.button('Generate Synthetic Calls', on_click=submit).classes('bg-primary text-white')
        

# ui.run()


