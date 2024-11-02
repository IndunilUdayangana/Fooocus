import gradio as gr
import random
import os
import json
import time
import shared
import modules.config
import fooocus_version
import modules.html
import modules.async_worker as worker
import modules.constants as constants
import modules.flags as flags
import modules.gradio_hijack as grh
import modules.style_sorter as style_sorter
import modules.meta_parser
import args_manager
import copy
import launch
from extras.inpaint_mask import SAMOptions

from modules.sdxl_styles import legal_style_names
from modules.private_logger import get_current_html_path
from modules.ui_gradio_extensions import reload_javascript
from modules.auth import auth_enabled, check_auth
from modules.util import is_json
import argparse


def generate_clicked(task: worker.AsyncTask):
    import ldm_patched.modules.model_management as model_management

    with model_management.interrupt_processing_mutex:
        model_management.interrupt_processing = False

    if len(task.args) == 0:
        return

    execution_start_time = time.perf_counter()
    finished = False
    generated_images = []

    # Start the task
    worker.async_tasks.append(task)

    while not finished:
        time.sleep(0.01)
        if len(task.yields) > 0:
            flag, product = task.yields.pop(0)
            if flag == 'preview':
                # Optional: Handle preview
                pass
            if flag == 'results':
                # Handle results
                generated_images = product
            if flag == 'finish':
                if not args_manager.args.disable_enhance_output_sorting:
                    product = sort_enhance_images(product, task)
                finished = True

                # Cleanup if needed
                if args_manager.args.disable_image_log:
                    for filepath in product:
                        if isinstance(filepath, str) and os.path.exists(filepath):
                            os.remove(filepath)

    execution_time = time.perf_counter() - execution_start_time
    print(f'Total time: {execution_time:.2f} seconds')
    return generated_images


def sort_enhance_images(images, task):
    if not task.should_enhance or len(images) <= task.images_to_enhance_count:
        return images

    sorted_images = []
    walk_index = task.images_to_enhance_count

    for index, enhanced_img in enumerate(images[:task.images_to_enhance_count]):
        sorted_images.append(enhanced_img)
        if index not in task.enhance_stats:
            continue
        target_index = walk_index + task.enhance_stats[index]
        if walk_index < len(images) and target_index <= len(images):
            sorted_images += images[walk_index:target_index]
        walk_index += task.enhance_stats[index]

    return sorted_images


# [False, 'STYLE: Close-up Shot Top view | EMOTION: Tempting I SCENE: Hot Fudge Sundae Brownie Cheesecake | TAGS: High-end food photography, clean composition, dramatic lighting, luxurious, elegant, mouth-watering, indulgent, gourmet | CAMERA: Nikon Z7 | FOCAL LENGTH: 50mm | SHOT TYPE: Close-up | COMPOSITION: Top view Centered | LIGHTING: Soft directional light | PRODUCTION: Food Stylist | TIME: Daytime I LOCATION TYPE: Kitchen near windows --ar 3:2\n\n', '', ['Fooocus V2', 'Fooocus Enhance', 'Fooocus Sharp', 'Fooocus Photograph', 'Fooocus Cinematic', 'Fooocus Semi Realistic'], 'Quality', '1216×832 <span style="color: grey;"> ∣ 19:13</span>', 1, 'jpeg', '7059970271479793701', False, 2, 4, 'juggernautXL_v8Rundiffusion.safetensors', 'None', 0.5, True, 'sd_xl_offset_example-lora_1.0.safetensors', 0.1, True, 'None', 1, True, 'None', 1, True, 'None', 1, True, 'None', 1, True, 'uov', 'Upscale (1.5x)', None, [], None, '', None, False, False, False, False, 1.5, 0.8, 0.3, 7, 2, 'dpmpp_2m_sde_gpu', 'karras', 'Default (model)', -1, -1, -1, -1, -1, -1, False, False, False, False, 64, 128, 'joint', 0.25, False, 1.01, 1.02, 0.99, 0.95, False, False, 'v2.6', 1, 0.618, False, False, 0, False, False, 'fooocus', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', False, 0, False, None, False, 'Disabled', 'Before First Enhancement', 'Original Prompts', False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False, False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False, False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False]

# Main execution
if __name__ == "__main__":

    # Parsing command-line arguments
    parser = argparse.ArgumentParser(description='Generate images using command-line arguments')
    parser.add_argument('--prompt', type=str, required=True, help='The prompt to use for image generation')
    parser.add_argument('--num_of_images', type=int, required=True, help='Number of images to generate')
    args_cli = parser.parse_args()
    
    # Create the task
    # task = get_task()
    # Manually set the arguments for the task
    args = [False, 'STYLE: Close-up Shot Top view | EMOTION: Tempting I SCENE: Hot Fudge Sundae Brownie Cheesecake | TAGS: High-end food photography, clean composition, dramatic lighting, luxurious, elegant, mouth-watering, indulgent, gourmet | CAMERA: Nikon Z7 | FOCAL LENGTH: 50mm | SHOT TYPE: Close-up | COMPOSITION: Top view Centered | LIGHTING: Soft directional light | PRODUCTION: Food Stylist | TIME: Daytime I LOCATION TYPE: Kitchen near windows --ar 3:2\n\n', '', ['Fooocus V2', 'Fooocus Enhance', 'Fooocus Sharp', 'Fooocus Photograph', 'Fooocus Cinematic', 'Fooocus Semi Realistic'], 'Quality', '1216×832 <span style="color: grey;"> ∣ 19:13</span>', 1, 'jpeg', '7059970271479793701', False, 2, 4, 'juggernautXL_v8Rundiffusion.safetensors', 'None', 0.5, True, 'sd_xl_offset_example-lora_1.0.safetensors', 0.1, True, 'None', 1, True, 'None', 1, True, 'None', 1, True, 'None', 1, True, 'uov', 'Upscale (1.5x)', None, [], None, '', None, False, False, False, False, 1.5, 0.8, 0.3, 7, 2, 'dpmpp_2m_sde_gpu', 'karras', 'Default (model)', -1, -1, -1, -1, -1, -1, False, False, False, False, 64, 128, 'joint', 0.25, False, 1.01, 1.02, 0.99, 0.95, False, False, 'v2.6', 1, 0.618, False, False, 0, False, False, 'fooocus', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', False, 0, False, None, False, 'Disabled', 'Before First Enhancement', 'Original Prompts', False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False, False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False, False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False]
        #  [False, 'city park, look up view cloudy sky, sunlights, 50mm lens, hyper realistic, landscape photography, magazine aesthetic, 16k, vibrant colors --style raw --ar 16:9 --v 6.0', '', ['Fooocus V2', 'Fooocus Enhance', 'Fooocus Sharp', 'Fooocus Semi Realistic', 'Fooocus Photograph', 'Fooocus Cinematic'], 'Quality', '1152×896 <span style="color: grey;"> ∣ 9:7</span>', 1, 'jpeg', '8985865377079148486', False, 2, 4, 'juggernautXL_v8Rundiffusion.safetensors', 'None', 0.5, True, 'sd_xl_offset_example-lora_1.0.safetensors', 0.1, True, 'None', 1, True, 'None', 1, True, 'None', 1, True, 'None', 1, True, 'uov', 'Upscale (2x)', None, [], None, '', None, False, False, False, False, 1.5, 0.8, 0.3, 7, 2, 'dpmpp_2m_sde_gpu', 'karras', 'Default (model)', -1, -1, -1, -1, -1, -1, False, False, False, False, 64, 128, 'joint', 0.25, False, 1.01, 1.02, 0.99, 0.95, False, False, 'v2.6', 1, 0.618, False, False, 0, False, False, 'fooocus', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', False, 0, False, None, False, 'Disabled', 'Before First Enhancement', 'Original Prompts', False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False, False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False, False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False]
        #  [False, 'city park, look up view cloudy sky, sunlights, 50mm lens, hyper realistic, landscape photography, magazine aesthetic, 16k, vibrant colors --style raw --ar 16:9 --v 6.0', '', ['Fooocus V2', 'Fooocus Enhance', 'Fooocus Sharp', 'Fooocus Semi Realistic', 'Fooocus Photograph', 'Fooocus Cinematic'], 'Quality', '1152×896 <span style="color: grey;"> ∣ 9:7</span>', 1, 'jpeg', '5448677538064554108', False, 2, 4, 'juggernautXL_v8Rundiffusion.safetensors', 'None', 0.5, True, 'sd_xl_offset_example-lora_1.0.safetensors', 0.1, True, 'None', 1, True, 'None', 1, True, 'None', 1, True, 'None', 1, True, 'uov', 'Upscale (2x)', None, [], None, '', None, False, False, False, False, 1.5, 0.8, 0.3, 7, 2, 'dpmpp_2m_sde_gpu', 'karras', 'Default (model)', -1, -1, -1, -1, -1, -1, False, False, False, False, 64, 128, 'joint', 0.25, False, 1.01, 1.02, 0.99, 0.95, False, False, 'v2.6', 1, 0.618, False, False, 0, False, False, 'fooocus', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', False, 0, False, None, False, 'Disabled', 'Before First Enhancement', 'Original Prompts', False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False, False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False, False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False]
        #  [False, 'city park, look up view cloudy sky, sunlights, 50mm lens, hyper realistic, landscape photography, magazine aesthetic, 16k, vibrant colors --style raw --ar 16:9 --v 6.0', '', ['Fooocus V2', 'Fooocus Enhance', 'Fooocus Sharp'], 'Speed', '1152×896 <span style="color: grey;"> ∣ 9:7</span>', 24, 'png', '8800040169824511047', False, 2, 4, 'juggernautXL_v8Rundiffusion.safetensors', 'None', 0.5, True, 'sd_xl_offset_example-lora_1.0.safetensors', 0.1, True, 'None', 1, True, 'None', 1, True, 'None', 1, True, 'None', 1, True, 'uov', 'Upscale (2x)', None, [], None, '', None, False, False, False, False, 1.5, 0.8, 0.3, 7, 2, 'dpmpp_2m_sde_gpu', 'karras', 'Default (model)', -1, -1, -1, -1, -1, -1, False, False, False, False, 64, 128, 'joint', 0.25, False, 1.01, 1.02, 0.99, 0.95, False, False, 'v2.6', 1, 0.618, False, False, 0, False, False, 'fooocus', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', None, 0.5, 0.6, 'ImagePrompt', False, 0, False, None, False, 'Disabled', 'Before First Enhancement', 'Original Prompts', False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False, False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False, False, '', '', '', 'sam', 'full', 'vit_b', 0.25, 0.3, 0, False, 'v2.6', 1, 0.618, 0, False]

     # Update args based on command-line input
    args[1] = args_cli.prompt  # Update the prompt (2nd item)
    args[6] = args_cli.num_of_images  # Update number of images (7th item)
    args[8] = random.randint(10**18, 10**19 - 1)  # Generate a random 19-digit number

    # Run the generation process
    generated_images = generate_clicked(worker.AsyncTask(args=args))
    
    # Output handling
    if generated_images:
        for idx, img_path in enumerate(generated_images):
            print(f"Generated image {idx + 1}: {img_path}")


