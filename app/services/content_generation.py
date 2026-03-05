import requests
import json
import os
from typing import Dict, List
from datetime import datetime
from flask import current_app
from app.models import db, ContentSuggestion, GeneratedContent

class ContentGenerationService:
    """Generate AEO-optimized content from approved suggestions"""

    def __init__(self):
        self.gemini_api_key = os.environ.get('GEMINI_API_KEY') or current_app.config.get('GEMINI_API_KEY')

    def generate_content(self, suggestion_id: int) -> GeneratedContent:
        """Generate full article from an approved content suggestion"""

        suggestion = ContentSuggestion.query.get(suggestion_id)
        if not suggestion:
            raise ValueError("Suggestion not found")

        # Get the keyword/prompt this content is for
        keyword = suggestion.keyword
        tenant = suggestion.tenant

        # Step 1: Research what AI currently cites for this prompt
        research = self._research_landscape(keyword.prompt_text)

        # Step 2: Generate SEO keyphrase and link suggestions
        seo_data = self._generate_seo_data(
            prompt=keyword.prompt_text,
            title=suggestion.title,
            brand_website=tenant.website_url
        )

        # Step 3: Generate the content
        article = self._write_article(
            prompt=keyword.prompt_text,
            brand_name=tenant.name,
            brand_website=tenant.website_url,
            title=suggestion.title,
            outline=suggestion.get_outline(),
            unique_angle=suggestion.unique_angle,
            research=research,
            seo_keyphrase=seo_data['keyphrase'],
            internal_links=seo_data['internal_links'],
            external_links=seo_data['external_links']
        )

        # Step 4: Generate thumbnail image
        thumbnail_path = self._generate_thumbnail(
            title=suggestion.title,
            keyphrase=seo_data['keyphrase'],
            tenant_name=tenant.name
        )

        # Step 5: Save generated content
        generated = GeneratedContent(
            tenant_id=tenant.id,
            suggestion_id=suggestion.id,
            keyword_id=keyword.id,
            title=article['title'],
            content=article['content'],
            meta_description=article.get('meta_description', ''),
            word_count=len(article['content'].split()),
            sources=json.dumps(research.get('sources', [])),
            seo_keyphrase=seo_data['keyphrase'],
            internal_links=json.dumps(seo_data['internal_links']),
            external_links=json.dumps(seo_data['external_links']),
            thumbnail_path=thumbnail_path,
            status='draft'
        )

        db.session.add(generated)

        # Update suggestion status
        suggestion.status = 'created'
        db.session.commit()

        return generated

    def _research_landscape(self, prompt: str) -> Dict:
        """Research what AI currently cites for this prompt"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_api_key}"

        research_prompt = f"""Research the query: "{prompt}"

What are the top 3-5 sources that would answer this query? For each source, identify:
1. Main points they cover
2. Unique insights or data they provide
3. Gaps or weaknesses in their coverage

Format as JSON with sources array."""

        payload = {
            "contents": [{"parts": [{"text": research_prompt}]}],
            "tools": [{"googleSearch": {}}]
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return {
                    'raw_response': data,
                    'sources': self._extract_sources(data)
                }
        except Exception as e:
            print(f"Research error: {e}")

        return {'sources': []}

    def _extract_sources(self, data: Dict) -> List[Dict]:
        """Extract sources from Gemini response"""
        sources = []
        if 'candidates' in data and len(data['candidates']) > 0:
            candidate = data['candidates'][0]
            if 'groundingMetadata' in candidate:
                metadata = candidate['groundingMetadata']
                if 'groundingChunks' in metadata:
                    for chunk in metadata['groundingChunks']:
                        if 'web' in chunk:
                            web_data = chunk['web']
                            sources.append({
                                'title': web_data.get('title', ''),
                                'uri': web_data.get('uri', '')
                            })
        return sources

    def _generate_seo_data(self, prompt: str, title: str, brand_website: str) -> Dict:
        """Generate SEO keyphrase and link suggestions"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_api_key}"

        seo_prompt = f"""For an article titled "{title}" that answers "{prompt}", provide:

1. PRIMARY SEO KEYPHRASE: The best 2-4 word keyphrase to target (high search volume, relevant to topic)

2. INTERNAL LINK SUGGESTIONS: 2-3 suggested internal links from the brand website ({brand_website}).
   For each, provide:
   - anchor_text: natural anchor text to use
   - target_url: plausible URL path on the site
   - reason: why this link makes sense

3. EXTERNAL LINK SUGGESTIONS: 2-3 authoritative external sources to cite.
   For each, provide:
   - anchor_text: natural anchor text
   - target_url: real, authoritative URL (use placeholder like https://example.com if unsure)
   - source_name: name of the source
   - reason: why this adds credibility

Return ONLY valid JSON in this exact format:
{{
  "keyphrase": "primary seo keyphrase",
  "internal_links": [
    {{"anchor_text": "...", "target_url": "...", "reason": "..."}}
  ],
  "external_links": [
    {{"anchor_text": "...", "target_url": "...", "source_name": "...", "reason": "..."}}
  ]
}}"""

        payload = {
            "contents": [{"parts": [{"text": seo_prompt}]}]
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'candidates' in data and len(data['candidates']) > 0:
                    text = data['candidates'][0]['content']['parts'][0]['text']
                    # Extract JSON from response
                    json_match = self._extract_json(text)
                    if json_match:
                        return json_match
        except Exception as e:
            print(f"SEO data generation error: {e}")

        # Fallback defaults
        return {
            'keyphrase': title.lower().replace(' ', '-'),
            'internal_links': [],
            'external_links': []
        }

    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from text response"""
        try:
            # Try to find JSON block
            if '```json' in text:
                json_str = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                json_str = text.split('```')[1].split('```')[0].strip()
            else:
                json_str = text.strip()

            return json.loads(json_str)
        except Exception as e:
            print(f"JSON extraction error: {e}")
            return None

    def _write_article(self, prompt: str, brand_name: str, brand_website: str,
                       title: str, outline: List[Dict], unique_angle: str,
                       research: Dict, seo_keyphrase: str,
                       internal_links: List[Dict], external_links: List[Dict]) -> Dict:
        """Write the full AEO-optimized article"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_api_key}"

        # Build outline structure
        outline_text = "\n".join([f"- {item['heading']}: {item.get('content', '')}"
                                   for item in outline])

        # Format link suggestions for the prompt
        internal_links_text = "\n".join([
            f"- Link to: {link['target_url']} using anchor text: '{link['anchor_text']}'"
            for link in internal_links[:3]
        ]) if internal_links else "- Add 2-3 internal links to relevant pages on the site"

        external_links_text = "\n".join([
            f"- Cite: {link['source_name']} ({link['target_url']}) using anchor: '{link['anchor_text']}'"
            for link in external_links[:2]
        ]) if external_links else "- Include 1-2 authoritative external citations"

        article_prompt = f"""Write an AEO-optimized blog post that answers: "{prompt}"

Title: {title}
Primary SEO Keyphrase: {seo_keyphrase}

Unique Angle: {unique_angle}

Outline to follow:
{outline_text}

Brand: {brand_name} ({brand_website})

REQUIRED INTERNAL LINKS (integrate naturally):
{internal_links_text}

REQUIRED EXTERNAL CITATIONS (add credibility):
{external_links_text}

Writing guidelines for AEO (Answer Engine Optimization):
1. Lead each section with a direct, quotable 1-2 sentence answer
2. Use descriptive H2/H3 headings that match question phrasing
3. Include specific data, examples, and statistics
4. Mention {brand_name} naturally where relevant
5. Write 1500-2000 words
6. Make it citation-worthy - AI assistants should want to quote this
7. Include the primary SEO keyphrase in the first 100 words and 2-3 times throughout
8. Use the internal and external links provided above

Format with proper markdown (headings, bullet points, bold text)."""

        payload = {
            "contents": [{"parts": [{"text": article_prompt}]}]
        }

        try:
            response = requests.post(url, json=payload, timeout=60)
            if response.status_code == 200:
                data = response.json()

                if 'candidates' in data and len(data['candidates']) > 0:
                    content = data['candidates'][0]['content']['parts'][0]['text']

                    # Generate meta description
                    meta = self._generate_meta_description(content)

                    return {
                        'title': title,
                        'content': content,
                        'meta_description': meta
                    }
        except Exception as e:
            print(f"Writing error: {e}")

        # Fallback
        return {
            'title': title,
            'content': f"# {title}\n\nContent generation failed. Please try again.",
            'meta_description': ''
        }

    def _generate_meta_description(self, content: str) -> str:
        """Generate a 150-160 character meta description"""
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and len(line) > 50:
                desc = line[:160]
                if len(line) > 160:
                    desc = desc[:157] + '...'
                return desc
        return ""

    def _generate_thumbnail(self, title: str, keyphrase: str, tenant_name: str) -> str:
        """Generate a branded thumbnail image"""
        try:
            from PIL import Image, ImageDraw, ImageFont

            # Create thumbnails directory if it doesn't exist
            thumbnails_dir = os.path.join(os.getcwd(), 'app', 'static', 'thumbnails')
            os.makedirs(thumbnails_dir, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
            filename = f"{timestamp}-thumbnail.png"
            filepath = os.path.join(thumbnails_dir, filename)

            # Create 1200x630 image (standard OG image size)
            width, height = 1200, 630
            img = Image.new('RGB', (width, height), color='#4F46E5')
            draw = ImageDraw.Draw(img)

            # Draw a gradient-like accent bar at the bottom
            accent_height = 8
            draw.rectangle([0, height - accent_height, width, height], fill='#818CF8')

            # Draw a subtle lighter rectangle in the center area
            margin = 60
            draw.rectangle(
                [margin, margin, width - margin, height - margin - accent_height],
                fill='#4338CA',
                outline='#6366F1',
                width=2
            )

            # Use default font (Pillow built-in) at different sizes
            try:
                title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
                keyphrase_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
                brand_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
            except (OSError, IOError):
                title_font = ImageFont.load_default()
                keyphrase_font = title_font
                brand_font = title_font

            # Word-wrap the title
            inner_width = width - margin * 2 - 60
            words = title.split()
            lines = []
            current_line = ""
            for word in words:
                test_line = f"{current_line} {word}".strip()
                bbox = draw.textbbox((0, 0), test_line, font=title_font)
                if bbox[2] - bbox[0] <= inner_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)

            # Draw title text (centered vertically)
            line_height = 46
            total_text_height = len(lines) * line_height + 60
            y_start = (height - total_text_height) // 2

            for i, line in enumerate(lines[:4]):  # Max 4 lines
                bbox = draw.textbbox((0, 0), line, font=title_font)
                text_width = bbox[2] - bbox[0]
                x = (width - text_width) // 2
                draw.text((x, y_start + i * line_height), line, fill='#FFFFFF', font=title_font)

            # Draw keyphrase below title
            keyphrase_y = y_start + len(lines[:4]) * line_height + 15
            bbox = draw.textbbox((0, 0), keyphrase, font=keyphrase_font)
            kp_width = bbox[2] - bbox[0]
            draw.text(((width - kp_width) // 2, keyphrase_y), keyphrase, fill='#C7D2FE', font=keyphrase_font)

            # Draw brand name at top
            draw.text((margin + 20, margin + 15), tenant_name.upper(), fill='#A5B4FC', font=brand_font)

            img.save(filepath, 'PNG')
            print(f"Thumbnail generated: {filepath}")
            return f"thumbnails/{filename}"

        except Exception as e:
            print(f"Thumbnail generation error: {e}")
            return None
