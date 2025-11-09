
import os
from zipfile import ZipFile
import datetime
import requests

def delete_files_except_zip(self, folder):
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            if os.path.isfile(file_path) and not filename.endswith('.zip'):
                os.remove(file_path)

def zip_files_in_folder(folder, zip_filename_root):
    zip_filename = f"{zip_filename_root}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.zip"
    with ZipFile(zip_filename, 'w') as zip:
        for filename in os.listdir(folder):
            if not filename.endswith('.zip'):
                file_path = os.path.join(folder, filename)
                zip.write(file_path, filename)
    return zip_filename


def remap_dimension(data_df, input_dimension_key, output_dimension_key, mapping_dict):
    fixed_categories = []
    categories = data_df[input_dimension_key]
    for category in categories:
        #for each key, value in mapping_dict, check if category is in key. if yes, change catergory to value
        to_append = "nan"
        for key, value in mapping_dict.items():
            if key in category:
                to_append = value
                break
        fixed_categories.append(to_append)
    data_df[output_dimension_key] = fixed_categories
    return data_df

def split_raw_category(project_df, number_of_categories, input_dimension_key):

    cat_dict = dict()
    for i in range(number_of_categories):
        cat_dict[i] = list()
    for catstring in project_df[input_dimension_key]:
        s_catstring = catstring.split(",")
        for i in range(number_of_categories):
                try:
                    cat = s_catstring[i]
                    cat_dict[i].append(cat)
                except:
                    cat_dict[i].append("nan")
    
    for i in range(number_of_categories):
        project_df[f'{input_dimension_key}{i}'] = cat_dict[i]

    return project_df

def strip_by_dimension(project_df, orga_df, dimension_key, value):
    project_df = project_df[project_df[dimension_key] != "nan"]
    orga_df = orga_df[orga_df["projectID"].isin(project_df["id"])]
    return project_df, orga_df

def send_teams_message(webhook_url: str, message: str) -> bool:
    """Send a message to a Microsoft Teams channel via Incoming Webhook.
    
    How to Create a Microsoft Teams Webhook URL:

    1. Open Microsoft Teams and go to the desired team and channel.
    2. Click (⋮) More options → Connectors.
    3. Find and select "Incoming Webhook" → Click Configure.
    4. Enter a name (e.g., "Connect Monitor Bot") and upload an optional icon.
    5. Click "Create" and copy the generated Webhook URL.
    6. Use this URL in your Python script to send messages.
    """
    try:
        res = requests.post(webhook_url, json={"text": message}, timeout=5)
        res.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Error: {e}")
        return False