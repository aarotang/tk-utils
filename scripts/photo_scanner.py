#!/usr/bin/env python3
# scripts/photo_scanner.py

import os
import re
from pathlib import Path
from datetime import datetime
from PIL import Image
import pytesseract
import json

class KingdomStoryPhotoScanner:
    def __init__(self):
        self.announcements_path = Path('announcements')
        self.character_keywords = ['新武將', 'New Officer', '新角色', 'New Character']
        self.event_keywords = ['活動', 'Event', '事件']
        self.maintenance_keywords = ['維護', 'Maintenance', '更新', 'Update']
        
    def preprocess_image(self, image_path):
        """Preprocess image for better OCR results"""
        try:
            import cv2
            import numpy as np
            
            # Read image
            image = cv2.imread(str(image_path))
            
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Apply gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (1, 1), 0)
            
            # Apply threshold to get better contrast
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Scale image up for better OCR (if image is small)
            height, width = thresh.shape
            if height < 500 or width < 500:
                scale_factor = 2
                thresh = cv2.resize(thresh, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
            
            # Convert back to PIL Image
            processed_image = Image.fromarray(thresh)
            return processed_image
            
        except Exception as e:
            print(f"Error preprocessing {image_path}: {e}")
            # Fallback to original image
            return Image.open(image_path)
        """Extract text from image using OCR"""
    def extract_text_from_image(self, image_path):
        """Extract text from image using OCR"""
        try:
            # Preprocess image for better OCR
            processed_image = self.preprocess_image(image_path)
            
            # Try multiple OCR configurations for better Chinese text extraction
            configs = [
                '--oem 3 --psm 3 -l chi_tra+eng',  # Traditional Chinese + English, auto page segmentation
                '--oem 3 --psm 6 -l chi_sim+eng',  # Simplified Chinese + English, single text block
                '--oem 3 --psm 4 -l chi_tra+chi_sim+eng',  # Both Chinese + English, single column
                '--oem 1 --psm 3 -l chi_tra+eng',  # Legacy engine for traditional Chinese
            ]
            
            best_text = ""
            max_length = 0
            
            # Try each configuration and keep the longest result
            for config in configs:
                try:
                    text = pytesseract.image_to_string(processed_image, config=config)
                    if len(text) > max_length:
                        max_length = len(text)
                        best_text = text
                except:
                    continue
            
            # Clean up the text
            if best_text:
                # Remove excessive whitespace and weird characters
                import re
                best_text = re.sub(r'\s+', ' ', best_text)  # Multiple spaces to single
                best_text = re.sub(r'[^\w\s\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff!@#$%^&*(),.?":{}|<>]', '', best_text)  # Keep Chinese, Japanese, alphanumeric, common punctuation
                best_text = best_text.strip()
            
            return best_text
            
        except Exception as e:
            print(f"Error extracting text from {image_path}: {e}")
            return ""

    def analyze_announcement_type(self, text):
        """Determine announcement type from extracted text"""
        text_lower = text.lower()
        
        if any(keyword in text for keyword in self.character_keywords):
            return "New Character"
        elif any(keyword in text for keyword in self.event_keywords):
            return "Event"
        elif any(keyword in text for keyword in self.maintenance_keywords):
            return "Maintenance"
        else:
            return "General Update"

    def extract_character_name(self, text):
        """Try to extract character name from text"""
        # Look for names in quotes or brackets
        patterns = [
            r'[「『]([^」』]+)[」』]',  # Japanese/Chinese quotes
            r'"([^"]+)"',              # English quotes
            r'【([^】]+)】',            # Chinese brackets
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                if len(name) > 1 and not name.isdigit():
                    return name
        
        return None

    def scan_announcement_folder(self, folder_path):
        """Scan a single announcement folder for images and generate content"""
        images_dir = folder_path / 'images'
        if not images_dir.exists():
            return None
            
        # Find all image files
        image_files = []
        supported_formats = {'.jpg', '.jpeg', '.png', '.gif'}
        
        for file_path in images_dir.iterdir():
            if file_path.suffix.lower() in supported_formats:
                image_files.append(file_path)
        
        if not image_files:
            return None
            
        # Sort images by name
        image_files.sort(key=lambda x: x.name)
        
        # Extract text from all images
        all_text = []
        for image_path in image_files:
            text = self.extract_text_from_image(image_path)
            if text:
                all_text.append(text)
        
        combined_text = ' '.join(all_text)
        
        # Analyze content
        announcement_type = self.analyze_announcement_type(combined_text)
        character_name = self.extract_character_name(combined_text)
        
        # Generate announcement data
        announcement_data = {
            'folder_name': folder_path.name,
            'type': announcement_type,
            'character_name': character_name,
            'image_files': [img.name for img in image_files],
            'extracted_text': combined_text[:500] + '...' if len(combined_text) > 500 else combined_text,
            'date': datetime.now().strftime('%Y-%m-%d')
        }
        
        return announcement_data

    def generate_announcement_readme(self, announcement_data, folder_path):
        """Generate README.md for individual announcement"""
        folder_name = announcement_data['folder_name']
        ann_type = announcement_data['type']
        char_name = announcement_data['character_name']
        image_files = announcement_data['image_files']
        
        # Create title
        if char_name:
            title = f"{ann_type} - {char_name}"
        else:
            title = f"Kingdom Story {ann_type}"
            
        # Generate markdown content
        markdown = f"""# {title}

**Date:** {announcement_data['date']}  
**Type:** {ann_type}  
**Status:** Active  

## Announcement Images

"""
        
        # Add all images
        for i, image_file in enumerate(image_files, 1):
            markdown += f"### Image {i}\n"
            markdown += f"![{ann_type} Image {i}](images/{image_file})\n\n"
        
        # Add extracted text section if available
        if announcement_data['extracted_text']:
            markdown += f"""## Extracted Text

```
{announcement_data['extracted_text']}
```

"""
        
        markdown += f"""## Notes

- Images automatically detected and processed
- Text extracted using OCR technology
- For detailed information, please refer to the original announcement images

---

*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        return markdown

    def update_main_readme(self, all_announcements):
        """Update the main announcements/README.md file"""
        readme_path = self.announcements_path / 'README.md'
        
        # Sort announcements by date (newest first)
        sorted_announcements = sorted(all_announcements, 
                                    key=lambda x: x['folder_name'], 
                                    reverse=True)
        
        # Generate main README content
        markdown = """# Kingdom Story Game Announcements

Welcome to the Kingdom Story announcements archive! This directory contains all official game updates, new character releases, events, and maintenance notices.

## 📋 Quick Navigation

- [Latest Updates](#latest-updates)
- [All Announcements](#all-announcements)
- [Categories](#categories)

## 🆕 Latest Updates

"""
        
        # Add latest 3 announcements
        for announcement in sorted_announcements[:3]:
            folder_name = announcement['folder_name']
            ann_type = announcement['type']
            char_name = announcement['character_name']
            date = announcement['date']
            
            title = f"{ann_type} - {char_name}" if char_name else ann_type
            markdown += f"- **[{date}]** - [{title}]({folder_name}/) - {ann_type}\n"
        
        markdown += "\n## 📁 All Announcements\n\n"
        markdown += "| Date | Type | Title | Link |\n"
        markdown += "|------|------|-------|------|\n"
        
        # Add all announcements to table
        for announcement in sorted_announcements:
            folder_name = announcement['folder_name']
            ann_type = announcement['type']
            char_name = announcement['character_name']
            date = announcement['date']
            
            title = f"{char_name}" if char_name else ann_type
            markdown += f"| {date} | {ann_type} | {title} | [View →]({folder_name}/) |\n"
        
        # Add categories section
        markdown += "\n## 🏷️ Categories\n\n"
        
        # Group by type
        by_type = {}
        for announcement in sorted_announcements:
            ann_type = announcement['type']
            if ann_type not in by_type:
                by_type[ann_type] = []
            by_type[ann_type].append(announcement)
        
        for ann_type, announcements in by_type.items():
            icon = "🎭" if ann_type == "New Character" else "🎉" if ann_type == "Event" else "🔧"
            markdown += f"### {icon} {ann_type}\n"
            
            for announcement in announcements:
                folder_name = announcement['folder_name']
                char_name = announcement['character_name']
                date = announcement['date']
                
                title = char_name if char_name else ann_type
                markdown += f"- [{title}]({folder_name}/) - {date}\n"
            
            markdown += "\n"
        
        markdown += f"""---

*Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*  
*Total Announcements: {len(all_announcements)}*
"""
        
        # Write the file
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        print(f"✅ Updated main README with {len(all_announcements)} announcements")

    def run(self):
        """Main scanning function"""
        print("🔍 Scanning for announcement photos...")
        
        if not self.announcements_path.exists():
            print("❌ Announcements directory not found!")
            return
        
        all_announcements = []
        
        # Scan each announcement folder
        for item in self.announcements_path.iterdir():
            if item.is_dir() and not item.name.startswith('.') and item.name != 'archive':
                print(f"📂 Scanning folder: {item.name}")
                
                announcement_data = self.scan_announcement_folder(item)
                if announcement_data:
                    all_announcements.append(announcement_data)
                    
                    # Generate individual README
                    readme_content = self.generate_announcement_readme(announcement_data, item)
                    readme_path = item / 'README.md'
                    
                    with open(readme_path, 'w', encoding='utf-8') as f:
                        f.write(readme_content)
                    
                    print(f"✅ Updated {item.name}/README.md")
        
        # Update main README
        if all_announcements:
            self.update_main_readme(all_announcements)
        
        print(f"🎉 Processed {len(all_announcements)} announcement folders")

if __name__ == "__main__":
    scanner = KingdomStoryPhotoScanner()
    scanner.run()
