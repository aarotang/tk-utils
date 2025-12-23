"""
Enhanced Kingdom Story Photo Scanner
Processes announcement images and generates well-formatted README files
Automatically detects Chinese names using Pinyin matching
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
# New import for automatic name matching
from pypinyin import lazy_pinyin

class KingdomStoryPhotoScanner:
    def __init__(self):
        self.announcement_dirs = []
        self.new_entries = []
        self.processed_folders = set()
       
        # OCR configuration: Prioritize Traditional Chinese, then English
        self.ocr_config = r'--oem 3 --psm 6 -l chi_tra+eng'
       
        # Common OCR error patterns and corrections
        self.text_corrections = {
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
            pil_image = Image.open(image_path)
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
           
            # Enhance contrast and sharpness
            enhancer = ImageEnhance.Contrast(pil_image)
            pil_image = enhancer.enhance(1.2)
            enhancer = ImageEnhance.Sharpness(pil_image)
            pil_image = enhancer.enhance(1.1)
           
            import numpy as np
            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
           
            # Adaptive thresholding
            processed = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            processed = cv2.medianBlur(processed, 3)
            return processed
           
        except Exception as e:
            print(f"Error preprocessing {image_path}: {e}")
            return cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)

    def extract_text_from_image(self, image_path):
        try:
            processed_image = self.preprocess_image(image_path)
            if processed_image is None: return ""
            text = pytesseract.image_to_string(processed_image, config=self.ocr_config)
            return self.clean_ocr_text(text)
        except Exception as e:
            print(f"Error extracting text from {image_path}: {e}")
            return ""

    def clean_ocr_text(self, text):
        if not text.strip(): return ""
        cleaned = text.strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = re.sub(r'\n\s*\n', '\n', cleaned)
       
        for correct, variations in self.text_corrections.items():
            for variation in variations:
                cleaned = cleaned.replace(variation, correct)
       
        lines = cleaned.split('\n')
        filtered_lines = []
        for line in lines:
            line = line.strip()
            if len(line) < 2: continue # Allow short Chinese names (2 chars)
            # Relaxed filter: Allow lines with some special chars if they contain Chinese
            if re.search(r'[\u4e00-\u9fff]', line):
                filtered_lines.append(line)
            else:
                special_chars = len(re.findall(r'[^\w\s]', line))
                if len(line) > 0 and special_chars / len(line) < 0.5:
                    filtered_lines.append(line)
       
        return '\n'.join(filtered_lines[:20])

    def determine_announcement_type(self, folder_name, extracted_text):
        """Determine type using generic keywords instead of specific names"""
        character_score = 0
        balance_score = 0  
        event_score = 0
       
        clean_folder = folder_name.lower()
        text_lower = extracted_text.lower() if extracted_text else ""
       
        # 1. GENERIC KEYWORDS (Permanent, no updates needed)
        character_keywords = [
            # English Types
            'new', 'character', 'hero', 'general', 'warrior',
            'emperor', 'legend', 'mythic', 'transcend', 'awaken',
            'rarity', 'costume', 'skin', 'avatar',
            # Chinese Types
            '新武將', '武將', '介紹', '登場', '角色'
        ]
       
        balance_keywords = [
            'balance', 'rework', 'update', 'adjustment', 'patch',
            'buff', 'nerf', 'revamp', 'remake', 'class',
            '平衡', '更新', '調整', '重做', '技能修改'
        ]
       
        event_keywords = [
            'event', 'limited', 'special', 'celebration', 'festival',
            '活動', '限時', '特別'
        ]

        # Score folder name
        for kw in character_keywords:
            if kw in clean_folder: character_score += 3
        for kw in balance_keywords:
            if kw in clean_folder: balance_score += 3
        for kw in event_keywords:
            if kw in clean_folder: event_score += 3
           
        # Score OCR text
        for kw in character_keywords:
            if kw in text_lower: character_score += 2
        for kw in balance_keywords:
            if kw in text_lower: balance_score += 2
        for kw in event_keywords:
            if kw in text_lower: event_score += 2

        # Specific patterns
        if re.search(r'技能[1-4]', text_lower):
            # Mentions skills -> likely character or balance
            character_score += 1
            balance_score += 1
           
        if re.search(r'v?\d+\.\d+', clean_folder):
            balance_score += 2

        # Decision
        scores = {
            'New Character Release': character_score,
            'Balance Update': balance_score,
            'Event Announcement': event_score
        }
       
        max_score = max(scores.values())
        max_types = [t for t, s in scores.items() if s == max_score]
       
        if max_score >= 2:
            if 'New Character Release' in max_types: return 'New Character Release'
            if 'Balance Update' in max_types: return 'Balance Update'
            return 'Event Announcement'
           
        # Fallback: If folder has a date but no obvious keywords, assume generic
        return 'Unknown - Requires Manual Review'

    def extract_date_from_folder(self, folder_name):
        date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', folder_name)
        if date_match:
            year, month, day = date_match.groups()
            return datetime(int(year), int(month), int(day)).strftime("%B %d, %Y")
       
        date_match = re.search(r'(\d{4})-(\d{1,2})', folder_name)
        if date_match:
            year, month = date_match.groups()
            return datetime(int(year), int(month), 1).strftime("%B %Y")
       
        return datetime.now().strftime("%B %d, %Y")

    def generate_title_from_folder(self, folder_name, announcement_type, extracted_text):
        """Generate title by matching folder English name to OCR Chinese Pinyin"""
       
        # Clean folder name
        clean_name = re.sub(r'^\d{4}-\d{1,2}-\d{1,2}-?', '', folder_name)
        clean_name = re.sub(r'^\d{4}-\d{1,2}-?', '', clean_name)
        title_base = clean_name.replace('-', ' ').replace('_', ' ').title()
       
        if announcement_type == "New Character Release":
            found_chinese_name = ""
           
            # 1. Try strict regex first (most accurate)
            char_match = re.search(r'新武將[：:\s]+([^\s\n]+)', extracted_text)
            if char_match:
                found_chinese_name = char_match.group(1)
           
            # 2. If strict fail, try Pinyin Matching (Automatic)
            if not found_chinese_name:
                # Prepare target: Remove generic words from title_base
                ignore_words = [
                    'emperor', 'rarity', 'legend', 'new', 'character', 'hero',
                    'skin', 'costume', 'general', 'warrior', 'awakened'
                ]
               
                # Get the core name parts (e.g., "Jiang Wei" from "Emperor Rarity Jiang Wei")
                target_parts = [w.lower() for w in title_base.split() if w.lower() not in ignore_words]
                target_pinyin = "".join(target_parts) # e.g. "jiangwei"
               
                if target_pinyin:
                    # Find all potential Chinese words (2-4 chars) in OCR text
                    # Include common surnames/names
                    candidates = re.findall(r'[\u4e00-\u9fff]{2,4}', extracted_text)
                   
                    for candidate in candidates:
                        # Convert candidate to pinyin
                        # lazy_pinyin returns list ['jiang', 'wei'] -> join to 'jiangwei'
                        cand_pinyin = "".join(lazy_pinyin(candidate))
                       
                        # Check for match
                        # 1. Exact match
                        # 2. Target inside Candidate (e.g. target="lubu", cand="shenlubu")
                        # 3. Candidate inside Target (rare)
                        if target_pinyin == cand_pinyin or \
                           (len(target_pinyin) > 3 and target_pinyin in cand_pinyin):
                            found_chinese_name = candidate
                            break

            if found_chinese_name:
                return f"新武將介紹 - {found_chinese_name} ({title_base})"
            else:
                return f"新武將介紹 - {title_base} (New Character Release)"
       
        elif announcement_type == "Balance Update":
            if 'warrior' in folder_name.lower() and 'class' in folder_name.lower():
                return "Warrior Class Rework (戰士職業重做)"
            elif 'rework' in folder_name.lower():
                return f"{title_base} Rework ({title_base}重做)"
            else:
                version_match = re.search(r'(\d+[a-z]?)', title_base)
                if version_match:
                    return f"Balance Update - {version_match.group(1)} (平衡更新)"
                return f"Balance Update - {title_base} (平衡更新)"
       
        else:
            return title_base

    def extract_skills_from_text(self, text):
        if not text: return []
        skills = []
        lines = text.split('\n')
       
        for i, line in enumerate(lines):
            line = line.strip()
            if not line: continue
           
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
                    description_lines = [skill_name] if skill_name else []
                   
                    for j in range(i+1, min(i+4, len(lines))):
                        next_line = lines[j].strip()
                        if not next_line or re.search(r'技能[1-4]', next_line):
                            break
                        if len(next_line) > 5:
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
        folder_name = folder_path.name
        all_text = '\n'.join(extracted_texts)
       
        announcement_type = self.determine_announcement_type(folder_name, all_text)
        title = self.generate_title_from_folder(folder_name, announcement_type, all_text)
        date = self.extract_date_from_folder(folder_name)
       
        content = f"# {title}\n"
        content += f"**Date:** {date}\n"
        content += f"**Type:** {announcement_type}\n"
       
        if announcement_type == "Balance Update":
            content += f"**Status:** Active\n"
        elif announcement_type == "New Character Release":
            content += f"**Event:** Special Release\n"
       
        content += "\n## Announcement Images\n"
       
        for i, img in enumerate(images, 1):
            if announcement_type == "New Character Release":
                desc = "Main Announcement" if i == 1 else f"Character Introduction {i}"
            elif announcement_type == "Balance Update":
                desc = "Main Announcement" if i == 1 else f"Balance Update Image {i}"
            else:
                desc = f"Announcement Image {i}"
            content += f"![{desc}](images/{img.name})\n"
       
        content += "\n## Summary\n"
       
        if announcement_type == "New Character Release":
            skills = self.extract_skills_from_text(all_text)
            if skills and len(skills) >= 2:
                content += f"- New character: {title.split(' - ')[1].split(' (')[0] if ' - ' in title else 'New Character'}\n"
                content += f"- Event type: Special Character Release\n"
                for skill in skills:
                    if skill['description'] and len(skill['description']) > 5:
                        content += f"- 技能{skill['number']}【{skill['name']}】：{skill['description']}\n"
            else:
                content += "New character release with unique abilities and skills.\n"
                content += "\nFor detailed skill information, please refer to the announcement images above.\n"
       
        elif announcement_type == "Balance Update":
            if 'warrior' in folder_name.lower():
                content += "This update focuses on warrior class adjustments.\n"
            else:
                skills = self.extract_skills_from_text(all_text)
                if skills:
                    content += "Character balance adjustments including:\n\n"
                    for skill in skills:
                        content += f"**技能{skill['number']} Changes:** {skill['description'][:100]}...\n\n"
                else:
                    content += "Balance update with character skill and parameter adjustments.\n"
        else:
            content += "General game announcement with important updates and information.\n"
       
        content += "\n## Notes\n"
        content += "- Images automatically detected and processed\n"
        content += "- For detailed information, please refer to the original announcement images above\n"
        content += "\n---\n"
        content += f"*Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
       
        return content

    def parse_date_from_line(self, line):
        date_match = re.search(r'\*\*([^*]+)\*\*', line)
        if not date_match: return datetime.min
        date_str = date_match.group(1).strip()
        formats = ["%b %d, %Y", "%B %d, %Y", "%b %Y", "%B %Y", "%Y-%m-%d"]
        for fmt in formats:
            try: return datetime.strptime(date_str, fmt)
            except ValueError: continue
        return datetime.min

    def update_main_readme(self):
        """Update announcements/README.md"""
        main_readme_path = Path("announcements/README.md")
        if not main_readme_path.exists() or not self.new_entries: return
       
        with open(main_readme_path, 'r', encoding='utf-8') as f: content = f.read()
       
        match = re.search(r'(### Recent Announcements\n)(.*?)(\n📋)', content, re.DOTALL)
        if not match: return
       
        new_lines = []
        for entry in self.new_entries:
            display_date = entry['date']
            try:
                if ',' in entry['date']:
                    display_date = datetime.strptime(entry['date'], "%B %d, %Y").strftime("%b %d, %Y")
                else:
                    display_date = datetime.strptime(entry['date'], "%B %Y").strftime("%b %Y")
            except: pass
            new_lines.append(f"- **{display_date}** - [{entry['title']}]({entry['folder']}/README.md) - {entry['type']}")
       
        existing_lines = [l.strip() for l in match.group(2).split('\n') if l.strip().startswith('- **')]
        all_lines = new_lines + existing_lines
       
        # Dedup
        seen = set()
        unique = []
        for line in all_lines:
            folder_m = re.search(r'\(([^/)]+)/README\.md\)', line)
            if folder_m and folder_m.group(1) not in seen:
                seen.add(folder_m.group(1))
                unique.append(line)
            elif not folder_m and line not in unique:
                unique.append(line)
               
        unique.sort(key=self.parse_date_from_line, reverse=True)
       
        new_section = match.group(1) + '\n'.join(unique[:10]) + match.group(3)
        updated = content.replace(match.group(0), new_section)
       
        today = datetime.now().strftime("%B %d, %Y")
        updated = re.sub(r'\*\*Last Updated:\*\* [^\n]+', f'**Last Updated:** {today}', updated)
       
        with open(main_readme_path, 'w', encoding='utf-8') as f: f.write(updated)
        print(f"Updated announcements/README.md with {len(new_lines)} new entries")

    def update_main_root_readme(self):
        """Update root README.md"""
        main_readme_path = Path("README.md")
        if not main_readme_path.exists() or not self.new_entries: return
       
        with open(main_readme_path, 'r', encoding='utf-8') as f: content = f.read()
       
        match = re.search(r'(### Recent Announcements\n)(.*?)(\n📋)', content, re.DOTALL)
        if not match: return
       
        new_lines = []
        for entry in self.new_entries:
            display_date = entry['date']
            try:
                if ',' in entry['date']:
                    display_date = datetime.strptime(entry['date'], "%B %d, %Y").strftime("%b %d, %Y")
                else:
                    display_date = datetime.strptime(entry['date'], "%B %Y").strftime("%b %Y")
            except: pass
            new_lines.append(f"- **{display_date}** - [{entry['title']}](announcements/{entry['folder']}/README.md) - {entry['type']}")
       
        existing_lines = [l.strip() for l in match.group(2).split('\n') if l.strip().startswith('- **')]
        all_lines = new_lines + existing_lines
       
        seen = set()
        unique = []
        for line in all_lines:
            folder_m = re.search(r'announcements/([^/)]+)/README\.md', line)
            if folder_m and folder_m.group(1) not in seen:
                seen.add(folder_m.group(1))
                unique.append(line)
            elif not folder_m and line not in unique:
                unique.append(line)
               
        unique.sort(key=self.parse_date_from_line, reverse=True)
       
        new_section = match.group(1) + '\n'.join(unique[:5]) + match.group(3)
        updated = content.replace(match.group(0), new_section)
       
        today = datetime.now().strftime("%B %d, %Y")
        updated = re.sub(r'\*\*Last Updated:\*\* [^\n]+', f'**Last Updated:** {today}', updated)
       
        with open(main_readme_path, 'w', encoding='utf-8') as f: f.write(updated)
        print(f"Updated root README.md with {len(new_lines)} new entries")

    def process_folder(self, folder_path):
        print(f"Processing folder: {folder_path}")
        images_path = folder_path / "images"
        readme_path = folder_path / "README.md"
       
        if readme_path.exists():
            with open(readme_path, 'r', encoding='utf-8') as f:
                if "*Auto-generated on" not in f.read():
                    print(f"  Skipping - README exists and is not auto-generated")
                    return False
       
        image_files = sorted(list(images_path.glob("*.jpg")) +
                           list(images_path.glob("*.png")) +
                           list(images_path.glob("*.jpeg")))
       
        if not image_files: return False
       
        print(f"  Extracting text from images...")
        extracted_texts = []
        for img_path in image_files[:5]:
            text = self.extract_text_from_image(img_path)
            if text.strip(): extracted_texts.append(text)
       
        readme_content = self.generate_readme_content(folder_path, image_files, extracted_texts)
       
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        print(f"  Generated README.md")
       
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
        print("🔍 Kingdom Story Photo Scanner - Pinyin Enabled")
        print("=" * 50)
       
        folders = self.find_announcement_folders()
        if not folders:
            print("No announcement folders found")
            return
       
        processed_count = 0
        for folder in folders:
            if self.process_folder(folder):
                processed_count += 1
       
        if processed_count > 0:
            self.update_main_readme()
            self.update_main_root_readme()
            print(f"\n✅ Successfully processed {processed_count} folders")
        else:
            print("\n ℹ️ No new content to process")

if __name__ == "__main__":
    scanner = KingdomStoryPhotoScanner()
    scanner.run()
