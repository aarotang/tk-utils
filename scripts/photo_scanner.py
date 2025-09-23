#!/usr/bin/env python3
"""
Enhanced Kingdom Story Photo Scanner
Processes announcement images and generates well-formatted README files
"""

import os
import re
import cv2
import glob
import json
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract

class KingdomStoryPhotoScanner:
    def __init__(self):
        self.announcement_dirs = []
        self.new_entries = []
        self.processed_folders = set()
        
        # OCR configuration for better Chinese text recognition
        self.ocr_config = r'--oem 3 --psm 6 -l chi_tra+chi_sim+eng'
        
        # Common OCR error patterns and corrections
        self.text_corrections = {
            # Common OCR misreads for Chinese characters
            '技能1': ['技能1', '技能 1', '技能I', '技能l'],
            '技能2': ['技能2', '技能 2', '技能II', '技能ll'],
            '技能3': ['技能3', '技能 3', '技能III', '技能lll'],
            '技能4': ['技能4', '技能 4', '技能IV', '技能lV'],
            '傷害': ['傷害', '伤害', '傷寮', '伤寮'],
            '攻擊': ['攻擊', '攻击', '攻撃'],
            '對象': ['對象', '对象', '對像'],
            '秒': ['秒', '妙', 'ネ少'],
            '造成': ['造成', '道成'],
            '發動': ['發動', '发动', '發勤'],
            '獲得': ['獲得', '获得', '獲徳'],
            '增加': ['增加', '堌加'],
            '減少': ['減少', '减少'],
            '%': ['%', '％', '% ', ' %'],
        }

    def find_announcement_folders(self):
        """Find all announcement folders with images"""
        announcements_path = Path("announcements")
        if not announcements_path.exists():
            print("No announcements directory found")
            return []
        
        folders = []
        for folder in announcements_path.iterdir():
            if folder.is_dir() and not folder.name.startswith('.'):
                images_path = folder / "images"
                if images_path.exists():
                    image_files = list(images_path.glob("*.jpg")) + \
                                 list(images_path.glob("*.png")) + \
                                 list(images_path.glob("*.jpeg"))
                    if image_files:
                        folders.append(folder)
        
        return sorted(folders)

    def preprocess_image(self, image_path):
        """Enhanced image preprocessing for better OCR results"""
        try:
            # Load with PIL for better handling
            pil_image = Image.open(image_path)
            
            # Convert to RGB if needed
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Enhance contrast and sharpness
            enhancer = ImageEnhance.Contrast(pil_image)
            pil_image = enhancer.enhance(1.2)
            
            enhancer = ImageEnhance.Sharpness(pil_image)
            pil_image = enhancer.enhance(1.1)
            
            # Convert to OpenCV format
            import numpy as np
            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            
            # Convert to grayscale
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            
            # Apply adaptive thresholding for better text recognition
            processed = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            
            # Noise reduction
            processed = cv2.medianBlur(processed, 3)
            
            return processed
            
        except Exception as e:
            print(f"Error preprocessing {image_path}: {e}")
            # Fallback to original image
            return cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)

    def extract_text_from_image(self, image_path):
        """Extract text with improved preprocessing and error correction"""
        try:
            processed_image = self.preprocess_image(image_path)
            
            if processed_image is None:
                return ""
            
            # Extract text with multiple attempts
            text = pytesseract.image_to_string(processed_image, config=self.ocr_config)
            
            # Clean and correct text
            cleaned_text = self.clean_ocr_text(text)
            
            return cleaned_text
            
        except Exception as e:
            print(f"Error extracting text from {image_path}: {e}")
            return ""

    def clean_ocr_text(self, text):
        """Clean and correct common OCR errors"""
        if not text.strip():
            return ""
        
        # Basic cleaning
        cleaned = text.strip()
        
        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = re.sub(r'\n\s*\n', '\n', cleaned)  # Remove empty lines
        
        # Fix common OCR errors
        for correct, variations in self.text_corrections.items():
            for variation in variations:
                cleaned = cleaned.replace(variation, correct)
        
        # Remove lines that are mostly garbage (too many special characters)
        lines = cleaned.split('\n')
        filtered_lines = []
        for line in lines:
            line = line.strip()
            if len(line) < 3:  # Skip very short lines
                continue
            # Count special characters vs letters/Chinese characters
            special_chars = len(re.findall(r'[^\w\s\u4e00-\u9fff]', line))
            total_chars = len(line)
            if total_chars > 0 and special_chars / total_chars < 0.5:  # Less than 50% special chars
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines[:15])  # Limit to first 15 clean lines

    def determine_announcement_type(self, folder_name, extracted_text):
        """Determine the type of announcement based on folder name and content"""

        # Initialize scores
        character_score = 0
        balance_score = 0  
        event_score = 0
        
        # Remove date prefix from folder name for analysis
        clean_folder = re.sub(r'^\d{4}-\d{1,2}-\d{1,2}-?', '', folder_name.lower())
        text_lower = extracted_text.lower() if extracted_text else ""
        
        # FOLDER NAME SCORING (higher weight = 3 points)
        character_folder_keywords = [
            'new', 'character', 'hero', 'cheok', 'jun', 'sun', 'shang', 'xiang',
            '武將', 'hero', 'warrior-new', 'introduction'
        ]
        
        balance_folder_keywords = [
            'balance', 'rework', 'update', 'warrior-class', 'class', 
            '平衡', '更新', 'modification', 'adjustment', 'nerf', 'buff'
        ]
        
        event_folder_keywords = [
            'event', '活動', '限時', 'limited', 'special', 'celebration'
        ]

        # Score folder name keywords
        for keyword in character_folder_keywords:
            if keyword in clean_folder:
                character_score += 3
                
        for keyword in balance_folder_keywords:
            if keyword in clean_folder:
                balance_score += 3
                
        for keyword in event_folder_keywords:
            if keyword in clean_folder:
                event_score += 3
        
        # OCR TEXT SCORING (moderate weight = 2 points)
        character_text_keywords = [
            '新武將', '武將介紹', 'new character', '角色', '職業介紹',
            'character introduction', '新增角色', 'hero introduction'
        ]
        
        balance_text_keywords = [
            '平衡更新', 'balance update', '技能修改', 'skill modification',
            '技能1', '技能2', '技能3', '技能4', 'rework', '重做'
        ]
        
        event_text_keywords = [
            '活動', 'event', '限時', 'limited time', '特別', 'special event'
        ]

        # Score OCR text keywords
        for keyword in character_text_keywords:
            if keyword in text_lower:
                character_score += 2
                
        for keyword in balance_text_keywords:
            if keyword in text_lower:
                balance_score += 2
                
        for keyword in event_text_keywords:
            if keyword in text_lower:
                event_score += 2
        
        # SPECIAL PATTERNS (bonus points)
        # Character names pattern bonus
        if re.search(r'(cheok|jun|sun|shang|xiang|zhang|zhao|liu|cao)', clean_folder):
            character_score += 2
            
        # Version number pattern suggests balance update
        if re.search(r'v?\d+[a-z]?|version', clean_folder):
            balance_score += 2
            
        # Multiple skills mentioned suggests balance update
        skill_mentions = len(re.findall(r'技能[1-4]', text_lower))
        if skill_mentions >= 3:
            balance_score += 2
        elif skill_mentions >= 1:
            # Single skill mention could be character introduction
            character_score += 1

        # CLASSIFICATION LOGIC
        min_threshold = 3
        scores = {
            'New Character Release': character_score,
            'Balance Update': balance_score,
            'Event Announcement': event_score
        }
        
        # Find highest scoring type
        max_score = max(scores.values())
        max_types = [type_name for type_name, score in scores.items() if score == max_score]
        
        # If highest score meets threshold
        if max_score >= min_threshold:
            # If tied, use priority: Character > Balance > Event
            if 'New Character Release' in max_types:
                return 'New Character Release'
            elif 'Balance Update' in max_types:
                return 'Balance Update'
            else:
                return 'Event Announcement'
        
        # If no type meets threshold, return unknown
        return 'Unknown - Requires Manual Review'   


    def extract_date_from_folder(self, folder_name):
        """Extract date from folder name and format it properly"""
        # Try to find date pattern like 2025-08-13
        date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', folder_name)
        if date_match:
            year, month, day = date_match.groups()
            return datetime(int(year), int(month), int(day)).strftime("%B %d, %Y")
        
        # Try to find year-month pattern like 2025-08
        date_match = re.search(r'(\d{4})-(\d{1,2})', folder_name)
        if date_match:
            year, month = date_match.groups()
            return datetime(int(year), int(month), 1).strftime("%B %Y")
        
        # Default to current date
        return datetime.now().strftime("%B %d, %Y")

    def generate_title_from_folder(self, folder_name, announcement_type, extracted_text):
        """Generate a proper title from folder name and content"""
        # Remove date prefix from folder name
        clean_name = re.sub(r'^\d{4}-\d{1,2}-\d{1,2}-?', '', folder_name)
        clean_name = re.sub(r'^\d{4}-\d{1,2}-?', '', clean_name)
        
        # Replace hyphens with spaces and title case
        title_base = clean_name.replace('-', ' ').replace('_', ' ').title()
        
        # Try to extract character name from text for character releases
        if announcement_type == "New Character Release":
            # Look for character name patterns in Chinese
            char_match = re.search(r'新武將[：:]\s*([^\s\n]+)', extracted_text)
            if char_match:
                char_name = char_match.group(1)
                return f"新武將介紹 - {char_name} (New Character - {title_base})"
            elif 'cheok' in folder_name.lower() or 'jun' in folder_name.lower():
                return f"新武將介紹 - 拓跋京 (New Character - Cheok Jun-gyeong)"
            else:
                return f"新武將介紹 - {title_base} (New Character Release)"
        
        elif announcement_type == "Balance Update":
            # Look for version number or specific update type
            if 'warrior' in folder_name.lower() and 'class' in folder_name.lower():
                return "Warrior Class Rework (戰士職業重做)"
            elif 'rework' in folder_name.lower():
                return f"{title_base} Rework ({title_base}重做)"
            else:
                # Look for version number
                version_match = re.search(r'(\d+[a-z]?)', title_base)
                if version_match:
                    version = version_match.group(1)
                    return f"Balance Update - {version} (平衡更新 - {version})"
                else:
                    return f"Balance Update - {title_base} (平衡更新)"
        
        else:
            return title_base

    def extract_skills_from_text(self, text):
        """Extract skill information from OCR text - improved version"""
        if not text:
            return []
        
        skills = []
        lines = text.split('\n')
        
        # Look for skill patterns more flexibly
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Look for skill headers with various formats
            skill_patterns = [
                r'技能([1-4])[：:【]?([^】\n]*)',
                r'技能\s*([1-4])[：:【]?([^】\n]*)',
                r'Skill\s*([1-4])[：:]?([^\n]*)'
            ]
            
            for pattern in skill_patterns:
                skill_match = re.search(pattern, line)
                if skill_match:
                    skill_num = skill_match.group(1)
                    skill_name = skill_match.group(2).strip('】').strip()
                    
                    # Collect description from following lines
                    description_lines = [skill_name] if skill_name else []
                    
                    # Look at next few lines for description
                    for j in range(i+1, min(i+4, len(lines))):
                        next_line = lines[j].strip()
                        if not next_line or re.search(r'技能[1-4]', next_line):
                            break
                        # Only add lines that look like descriptions (contain Chinese or meaningful text)
                        if len(next_line) > 5 and (re.search(r'[\u4e00-\u9fff]', next_line) or 
                                                  re.search(r'[攻擊傷害發動對象秒獲得增加]', next_line)):
                            description_lines.append(next_line)
                    
                    if description_lines:
                        skills.append({
                            'number': skill_num,
                            'name': skill_name,
                            'description': ' '.join(description_lines)
                        })
                    break
        
        return skills

    def generate_readme_content(self, folder_path, images, extracted_texts):
        """Generate README content using the preferred template - improved to match manual quality"""
        folder_name = folder_path.name
        all_text = '\n'.join(extracted_texts)
        
        # Determine announcement details
        announcement_type = self.determine_announcement_type(folder_name, all_text)
        title = self.generate_title_from_folder(folder_name, announcement_type, all_text)
        date = self.extract_date_from_folder(folder_name)
        
        # Generate README content following the exact template format
        content = f"# {title}\n"
        content += f"**Date:** {date}\n"
        content += f"**Type:** {announcement_type}\n"
        
        # Add status or event info based on type
        if announcement_type == "Balance Update":
            content += f"**Status:** Active\n"
        elif announcement_type == "New Character Release":
            content += f"**Event:** Special Release\n"
        
        content += "\n## Announcement Images\n"
        
        # Add images with more descriptive names matching the template
        for i, img in enumerate(images, 1):
            img_name = img.name
            if announcement_type == "New Character Release":
                if i == 1:
                    desc = "Main Announcement"
                else:
                    desc = f"Character Introduction {i}"
            elif announcement_type == "Balance Update":
                if i == 1:
                    desc = "Main Announcement"
                else:
                    desc = f"Balance Update Image {i}"
            else:
                desc = f"Announcement Image {i}"
            
            content += f"![{desc}](images/{img_name})\n"
        
        content += "\n## Summary\n"
        
        # Generate better summary based on type and extracted skills
        if announcement_type == "New Character Release":
            skills = self.extract_skills_from_text(all_text)
            if skills and len(skills) >= 3:  # Only show skills if we found multiple ones
                content += f"- New character: {title.split(' - ')[1] if ' - ' in title else 'New Character'}\n"
                content += f"- Event type: Special Character Release\n"
                for skill in skills:
                    if skill['description'] and len(skill['description']) > 10:
                        content += f"- 技能{skill['number']}【{skill['name']}】：{skill['description']}\n"
            else:
                content += "New character release with unique abilities and skills.\n"
                content += "\nFor detailed skill information, please refer to the announcement images above.\n"
        
        elif announcement_type == "Balance Update":
            if 'warrior' in folder_name.lower() and 'class' in folder_name.lower():
                content += "This update focuses on comprehensive warrior class adjustments and improvements.\n\n"
                content += "**Key Changes:**\n"
                content += "- Warrior skill rebalancing\n"
                content += "- Combat mechanics adjustments\n"
                content += "- Performance optimizations\n"
            else:
                skills = self.extract_skills_from_text(all_text)
                if skills and len(skills) >= 2:
                    content += "Character balance adjustments including:\n\n"
                    for skill in skills:
                        if skill['description'] and len(skill['description']) > 10:
                            content += f"**技能{skill['number']} Changes:** {skill['description'][:100]}...\n\n"
                else:
                    content += "Balance update with character skill and parameter adjustments.\n"
                    content += "\nThis update includes various gameplay balance improvements and bug fixes.\n"
        
        else:
            content += "General game announcement with important updates and information.\n"
            content += "\nPlease refer to the announcement images above for detailed information.\n"
        
        # Add notes section (simplified)
        content += "\n## Notes\n"
        content += "- Images automatically detected and processed\n"
        content += "- For detailed information, please refer to the original announcement images above\n"
        
        content += "\n---\n"
        content += f"*Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        
        return content

    def parse_date_from_line(self, line):
        """Extract and parse date from a README line for sorting"""
        # Extract date from line like "- **Aug 5, 2025** - [title]..."
        date_match = re.search(r'\*\*([^*]+)\*\*', line)
        if not date_match:
            return datetime.min
        
        date_str = date_match.group(1).strip()
        
        # Try different date formats
        date_formats = [
            "%b %d, %Y",      # Aug 5, 2025
            "%B %d, %Y",      # August 5, 2025
            "%b %Y",          # Aug 2025
            "%B %Y",          # August 2025
            "%Y-%m-%d",       # 2025-08-05
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # If parsing fails, try to extract at least the year
        year_match = re.search(r'(\d{4})', date_str)
        if year_match:
            try:
                return datetime(int(year_match.group(1)), 1, 1)
            except:
                pass
        
        return datetime.min

    def update_main_readme(self):
        """Update the main announcements/README.md file with new entries"""
        main_readme_path = Path("announcements/README.md")
        
        if not main_readme_path.exists():
            print("Main README.md not found")
            return
        
        # Read current README
        with open(main_readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if not self.new_entries:
            return
        
        # Find the "Recent Announcements" section
        recent_section_pattern = r'(### Recent Announcements\n)(.*?)(\n📋)'
        match = re.search(recent_section_pattern, content, re.DOTALL)
        
        if not match:
            print("Could not find Recent Announcements section")
            return
        
        # Prepare new entries
        new_lines = []
        for entry in self.new_entries:
            # Format date for display
            try:
                # Try to parse the date and format it as "Aug 13, 2025"
                if entry['date'].count(',') > 0:  # Full date like "August 13, 2025"
                    date_obj = datetime.strptime(entry['date'], "%B %d, %Y")
                    display_date = date_obj.strftime("%b %d, %Y")
                else:  # Month/year only like "August 2025"
                    date_obj = datetime.strptime(entry['date'], "%B %Y")
                    display_date = date_obj.strftime("%b %Y")
            except:
                display_date = entry['date']
            
            # Create the entry line
            line = f"- **{display_date}** - [{entry['title']}]({entry['folder']}/README.md) - {entry['type']}"
            new_lines.append(line)
        
        # Get existing entries (if any)
        existing_content = match.group(2).strip()
        existing_lines = [line.strip() for line in existing_content.split('\n') if line.strip() and line.strip().startswith('- **')]
        
        # Combine new and existing entries, removing duplicates by folder name
        all_lines = new_lines + existing_lines
        seen_folders = set()
        unique_lines = []
        
        for line in all_lines:
            # Extract folder name from the line to check for duplicates
            folder_match = re.search(r'\(([^/)]+)/README\.md\)', line)
            if folder_match:
                folder_name = folder_match.group(1)
                if folder_name not in seen_folders:
                    seen_folders.add(folder_name)
                    unique_lines.append(line)
            else:
                # If we can't extract folder name, check for exact duplicates
                if line not in unique_lines:
                    unique_lines.append(line)
        
        # Sort all entries by date (newest first)
        unique_lines.sort(key=self.parse_date_from_line, reverse=True)
        
        # Keep only the most recent 10 entries
        unique_lines = unique_lines[:10]
        
        # Update the README content
        new_recent_content = match.group(1) + '\n'.join(unique_lines) + match.group(3)
        updated_content = content.replace(match.group(0), new_recent_content)
        
        # Update the "Last Updated" date
        today = datetime.now().strftime("%B %d, %Y")
        updated_content = re.sub(r'\*\*Last Updated:\*\* [^\n]+', f'**Last Updated:** {today}', updated_content)
        
        # Write back to file
        with open(main_readme_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"Updated main README.md with {len(new_lines)} new entries")

    def process_folder(self, folder_path):
        """Process a single announcement folder"""
        print(f"Processing folder: {folder_path}")
        
        images_path = folder_path / "images"
        readme_path = folder_path / "README.md"
        
        # Skip if README already exists and is not auto-generated
        if readme_path.exists():
            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if "*Auto-generated on" not in content:
                    print(f"  Skipping - README exists and is not auto-generated")
                    return False
        
        # Get all image files
        image_files = sorted(list(images_path.glob("*.jpg")) + 
                           list(images_path.glob("*.png")) + 
                           list(images_path.glob("*.jpeg")))
        
        if not image_files:
            print(f"  No images found in {images_path}")
            return False
        
        print(f"  Found {len(image_files)} images")
        
        # Check for manual text override
        text_override_path = folder_path / "text.txt"
        if text_override_path.exists():
            print(f"  Using manual text override from text.txt")
            with open(text_override_path, 'r', encoding='utf-8') as f:
                extracted_texts = [f.read()]
        else:
            # Extract text from images (limit to first 5 for performance)
            print(f"  Extracting text from images...")
            extracted_texts = []
            for img_path in image_files[:5]:  # Limit to first 5 images
                text = self.extract_text_from_image(img_path)
                if text.strip():
                    extracted_texts.append(text)
                    print(f"    Extracted text from {img_path.name}: {len(text)} chars")
        
        # Generate README content
        readme_content = self.generate_readme_content(folder_path, image_files, extracted_texts)
        
        # Write README
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"  Generated README.md")
        
        # Add to new entries for main README update
        all_text = ' '.join(extracted_texts)
        self.new_entries.append({
            'folder': folder_path.name,
            'title': self.generate_title_from_folder(
                folder_path.name, 
                self.determine_announcement_type(folder_path.name, all_text),
                all_text
            ),
            'date': self.extract_date_from_folder(folder_path.name),
            'type': self.determine_announcement_type(folder_path.name, all_text)
        })
        
        return True

    def run(self):
        """Main processing function"""
        print("🔍 Kingdom Story Photo Scanner - Enhanced Version")
        print("=" * 50)
        
        folders = self.find_announcement_folders()
        if not folders:
            print("No announcement folders found")
            return
        
        print(f"Found {len(folders)} announcement folders")
        
        processed_count = 0
        for folder in folders:
            if self.process_folder(folder):
                processed_count += 1
        
        if processed_count > 0:
            # Update main README instead of creating new-entries.md
            self.update_main_readme()
            print(f"\n✅ Successfully processed {processed_count} folders")
            print("📝 Updated main announcements/README.md")
        else:
            print("\n ℹ️ No new content to process")

if __name__ == "__main__":
    scanner = KingdomStoryPhotoScanner()
    scanner.run()
