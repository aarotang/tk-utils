#!/usr/bin/env python3
# scripts/photo_scanner.py

import os
import re
import json
from pathlib import Path
from datetime import datetime
from PIL import Image
import pytesseract

class KingdomStoryPhotoScanner:
    def __init__(self):
        self.announcements_path = Path('announcements')
        self.processing_log_path = Path('announcements/.processing-log.json')
        
        # Keywords for categorization
        self.character_keywords = ['新武將', 'New Officer', '新角色', 'New Character', '武將介紹']
        self.event_keywords = ['活動', 'Event', '事件', '慶典', 'Festival']
        self.maintenance_keywords = ['維護', 'Maintenance', '更新', 'Update']
        self.balance_keywords = ['平衡', 'Balance', '改版', 'Rework', '調整', 'Adjustment']
        
    def load_processing_log(self):
        """Load log of previously processed folders"""
        if self.processing_log_path.exists():
            try:
                with open(self.processing_log_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {'processed_folders': []}
        return {'processed_folders': []}
    
    def save_processing_log(self, log_data):
        """Save processing log"""
        with open(self.processing_log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

    def find_new_announcement_folders(self):
        """Find folders that need processing (no README.md)"""
        if not self.announcements_path.exists():
            return []
            
        new_folders = []
        processing_log = self.load_processing_log()
        processed = set(processing_log.get('processed_folders', []))
        
        for folder in self.announcements_path.iterdir():
            if (folder.is_dir() and 
                not folder.name.startswith('.') and 
                folder.name not in processed and
                folder.name != 'archive'):
                
                readme_path = folder / 'README.md'
                images_dir = folder / 'images'
                
                # Only process if no README exists but images directory does
                if not readme_path.exists() and images_dir.exists():
                    image_files = list(images_dir.glob('*.jpg')) + list(images_dir.glob('*.png')) + list(images_dir.glob('*.jpeg'))
                    if image_files:
                        new_folders.append(folder)
        
        return new_folders

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

    def extract_text_from_image(self, image_path):
        """Extract text from image using OCR"""
        try:
            # Check for manual text override first
            text_file = image_path.parent.parent / 'text.txt'
            if text_file.exists():
                with open(text_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            
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
                best_text = re.sub(r'\s+', ' ', best_text)  # Multiple spaces to single
                best_text = re.sub(r'[^\w\s\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff!@#$%^&*(),.?":{}|<>]', '', best_text)  # Keep Chinese, Japanese, alphanumeric, common punctuation
                best_text = best_text.strip()
            
            return best_text
            
        except Exception as e:
            print(f"Error extracting text from {image_path}: {e}")
            return ""

    def analyze_announcement_type(self, text, folder_name):
        """Determine announcement type from extracted text and folder name"""
        combined_text = (text + ' ' + folder_name).lower()
        
        if any(keyword in text for keyword in self.character_keywords):
            return "New Character"
        elif any(keyword in combined_text for keyword in self.balance_keywords):
            return "Balance Update"
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
            r'[（(]([^)）]+)[)）]',      # Parentheses
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                name = match.strip()
                # Filter out common non-name matches
                if (len(name) > 1 and len(name) < 20 and 
                    not name.isdigit() and 
                    not any(word in name.lower() for word in ['event', 'update', 'maintenance', '活動', '更新', '維護'])):
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
        announcement_type = self.analyze_announcement_type(combined_text, folder_path.name)
        character_name = self.extract_character_name(combined_text)
        
        # Extract date from folder name
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', folder_path.name)
        announcement_date = date_match.group(1) if date_match else datetime.now().strftime('%Y-%m-%d')
        
        # Generate announcement data
        announcement_data = {
            'folder_name': folder_path.name,
            'type': announcement_type,
            'character_name': character_name,
            'date': announcement_date,
            'image_files': [img.name for img in image_files],
            'extracted_text': combined_text[:1000] + '...' if len(combined_text) > 1000 else combined_text,
            'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return announcement_data

    def generate_announcement_readme(self, announcement_data, folder_path):
        """Generate README.md for individual announcement"""
        folder_name = announcement_data['folder_name']
        ann_type = announcement_data['type']
        char_name = announcement_data['character_name']
        image_files = announcement_data['image_files']
        announcement_date = announcement_data['date']
        
        # Create title
        if char_name:
            title = f"{ann_type} - {char_name}"
        else:
            title = f"Kingdom Story {ann_type}"
            
        # Generate markdown content
        markdown = f"""# {title}

**Date:** {announcement_date}  
**Type:** {ann_type}  
**Status:** Active  

## Announcement Images

"""
        
        # Add all images
        for i, image_file in enumerate(image_files, 1):
            markdown += f"### Image {i}\n"
            markdown += f"![{ann_type} Image {i}](images/{image_file})\n\n"
        
        # Add extracted text section if available and not too messy
        extracted_text = announcement_data['extracted_text']
        if extracted_text and len(extracted_text) > 20:
            # Only include if text seems reasonably clean
            clean_lines = [line.strip() for line in extracted_text.split('\n') if line.strip() and len(line.strip()) > 3]
            if clean_lines:
                markdown += f"""## Extracted Text Content

```
{chr(10).join(clean_lines[:10])}  # Limit to first 10 clean lines
{"..." if len(clean_lines) > 10 else ""}
```

> **Note:** Text extracted using OCR technology. Some characters may be inaccurate.

"""
        
        markdown += f"""## Notes

- Images automatically detected and processed
- To override OCR text extraction, create a `text.txt` file in this folder
- For detailed information, please refer to the original announcement images above

---

*Auto-generated on {announcement_data['processed_at']}*
"""
        
        return markdown

    def generate_new_entries_file(self, all_announcements):
        """Generate new-entries.md with proposed additions for main README"""
        if not all_announcements:
            return
        
        # Sort announcements by date (newest first)
        sorted_announcements = sorted(all_announcements, 
                                    key=lambda x: x['date'], 
                                    reverse=True)
        
        markdown = f"""# Proposed Additions for announcements/README.md

> **Instructions:** Copy the sections below and paste them into the appropriate places in `announcements/README.md`

## For "🆕 Latest Updates" Section

Add these entries to your "Recent Announcements" list:

"""
        
        # Add latest updates entries
        for announcement in sorted_announcements:
            folder_name = announcement['folder_name']
            ann_type = announcement['type']
            char_name = announcement['character_name']
            date = announcement['date']
            
            # Format date for display
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                display_date = date_obj.strftime('%b %d, %Y')
            except:
                display_date = date
            
            title = f"{ann_type} - {char_name}" if char_name else ann_type
            markdown += f"- **{display_date}** - [{title}]({folder_name}/) - {ann_type}\n"
        
        markdown += "\n## For \"📁 All Announcements\" Table\n\n"
        markdown += "Add these rows to your announcements table:\n\n"
        markdown += "```markdown\n"
        
        # Add table entries
        for announcement in sorted_announcements:
            folder_name = announcement['folder_name']
            ann_type = announcement['type']
            char_name = announcement['character_name']
            date = announcement['date']
            
            title = char_name if char_name else ann_type
            markdown += f"| {date} | {ann_type} | {title} | [View →]({folder_name}/) |\n"
        
        markdown += "```\n\n## For \"🏷️ Categories\" Section\n\n"
        
        # Group by type for categories
        by_type = {}
        for announcement in sorted_announcements:
            ann_type = announcement['type']
            if ann_type not in by_type:
                by_type[ann_type] = []
            by_type[ann_type].append(announcement)
        
        markdown += "Add these entries to the appropriate category sections:\n\n"
        
        for ann_type, announcements in by_type.items():
            # Determine icon
            if ann_type == "New Character":
                icon = "🎭"
            elif ann_type == "Event":
                icon = "🎉"
            elif ann_type == "Balance Update":
                icon = "⚖️"
            else:
                icon = "🔧"
                
            markdown += f"### {icon} {ann_type}\n"
            markdown += "```markdown\n"
            
            for announcement in announcements:
                folder_name = announcement['folder_name']
                char_name = announcement['character_name']
                date = announcement['date']
                
                # Format date for display
                try:
                    date_obj = datetime.strptime(date, '%Y-%m-%d')
                    display_date = date_obj.strftime('%b %d, %Y')
                except:
                    display_date = date
                
                title = char_name if char_name else ann_type
                markdown += f"- [{title}]({folder_name}/) - {display_date}\n"
            
            markdown += "```\n\n"
        
        markdown += f"""---

## Summary

**Generated {len(all_announcements)} new announcement(s):**

"""
        
        for announcement in sorted_announcements:
            markdown += f"- `{announcement['folder_name']}/` - {announcement['type']}\n"
        
        markdown += f"""

**Next Steps:**
1. Review the individual README files in each announcement folder
2. Edit any content that needs correction
3. Copy the desired entries above into your main `announcements/README.md`
4. Delete this `new-entries.md` file after integration
5. Merge this Pull Request

*Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        # Write the file
        with open('new-entries.md', 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        print(f"✅ Generated new-entries.md with {len(all_announcements)} proposed additions")

    def run(self):
        """Main scanning function - only process new folders"""
        print("🔍 Scanning for new announcement folders...")
        
        if not self.announcements_path.exists():
            print("❌ Announcements directory not found!")
            return
        
        # Find folders that need processing
        new_folders = self.find_new_announcement_folders()
        
        if not new_folders:
            print("ℹ️ No new announcement folders found to process")
            return
        
        print(f"📂 Found {len(new_folders)} new folders to process:")
        for folder in new_folders:
            print(f"  - {folder.name}")
        
        processed_announcements = []
        processing_log = self.load_processing_log()
        
        # Process each new folder
        for folder in new_folders:
            print(f"\n📸 Processing folder: {folder.name}")
            
            announcement_data = self.scan_announcement_folder(folder)
            if announcement_data:
                processed_announcements.append(announcement_data)
                
                # Generate individual README
                readme_content = self.generate_announcement_readme(announcement_data, folder)
                readme_path = folder / 'README.md'
                
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write(readme_content)
                
                # Add to processing log
                processing_log['processed_folders'].append(folder.name)
                
                print(f"✅ Generated {folder.name}/README.md")
            else:
                print(f"❌ Failed to process {folder.name}")
        
        if processed_announcements:
            # Generate new entries file for main README
            self.generate_new_entries_file(processed_announcements)
            
            # Update processing log
            self.save_processing_log(processing_log)
            
            print(f"\n🎉 Successfully processed {len(processed_announcements)} new announcement folders")
            print("📋 Created new-entries.md with proposed README additions")
            print("🔄 Pull Request will be created for your review")
        else:
            print("ℹ️ No announcements were successfully processed")

if __name__ == "__main__":
    scanner = KingdomStoryPhotoScanner()
    scanner.run()
