import base64
import os
import uuid
import re
from typing import Optional

def save_base64_image(base64_data: str, subfolder: str = "assets") -> Optional[str]:
    """
    Decodes a base64 image string and saves it to the uploads directory.
    Returns the relative URL path to the file.
    """
    if not base64_data or not base64_data.startswith("data:image"):
        return base64_data

    try:
        # 1. Extract the format and base64 parts
        # format: data:image/jpeg;base64,/9j/4AAQSk...
        header, encoded = base64_data.split(",", 1)
        
        # Determine extension from header
        match = re.search(r"data:image/(\w+);base64", header)
        extension = match.group(1) if match else "jpg"
        if extension == "jpeg":
            extension = "jpg"
            
        # 2. Prepare the storage path
        base_path = "uploads"
        target_dir = os.path.join(base_path, subfolder)
        os.makedirs(target_dir, exist_ok=True)
        
        filename = f"{uuid.uuid4()}.{extension}"
        file_path = os.path.join(target_dir, filename)
        
        # 3. Decode and save
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(encoded))
            
        # 4. Return the public relative URL
        return f"/{base_path}/{subfolder}/{filename}"
        
    except Exception as e:
        print(f"Error saving base64 image: {e}")
        return base64_data # Fallback to original if processing fails
