import theme
from nicegui import ui
import httpx
import os

async def ccai_status():
    with theme.frame('CCAI Log generation status'):
        ui.page_title('CCAI Log generation status')
        CLOUD_FUNCTION_URL = 'https://us-central1-gen-ai-4all.cloudfunctions.net/check_ccai_status'

        # Input field for group_id
        group_id_input = ui.input(label='Group ID').props('size=50 rounded outlined dense')

        # Output area to display the results
        output_area = ui.label()

        async def call_cloud_function_and_display_result():
            group_id = group_id_input.value
            if not group_id:
                output_area.text = 'Please enter a Group ID'
                return

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f'{CLOUD_FUNCTION_URL}?group_id={group_id}')
                    response.raise_for_status()  # Raise an exception for error statuses
                    data = response.json()

                message = data.get('message', 'Unknown response')
                status_counts = data.get('status_counts', {})
                signed_url = data.get('signed_url', '')

                output_area.text = f'Message: {message}'
                for status, count in status_counts.items():
                    output_area.text += f'{status}: {count}\n'
                if signed_url:
                    output_area.text += 'Signed URL: ' 
                    ui.link('Download File', signed_url).classes('text-blue-500') 

            except httpx.RequestError as e:
                output_area.text = f'Error: {e}'

        # Button to trigger the Cloud Function call
        ui.button('Get Task Status', on_click=call_cloud_function_and_display_result)