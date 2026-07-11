#!/usr/bin/env python3
"""Generate a professional Alpha Stack PDF report using WeasyPrint."""

import os
from weasyprint import HTML

# Read the markdown content
with open('alphastack_full_research.md', 'r') as f:
    content = f.read()

# Convert markdown to basic HTML
def md_to_html(md):
    lines = md.split('\n')
    html_parts = []
    in_table = False
    in_list = False
    table_rows = []
    
    for line in lines:
        stripped = line.strip()
        
        if not stripped:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            if in_table:
                html_parts.append(build_table(table_rows))
                table_rows = []
                in_table = False
            html_parts.append('<br/>')
            continue
        
        # Tables
        if '|' in stripped and stripped.startswith('|'):
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if all(c.replace('-', '').replace(':', '') == '' for c in cells):
                continue
            in_table = True
            table_rows.append(cells)
            continue
        elif in_table:
            html_parts.append(build_table(table_rows))
            table_rows = []
            in_table = False
        
        # Headers
        if stripped.startswith('# ') and not stripped.startswith('## '):
            text = stripped[2:].strip()
            html_parts.append(f'<h1>{text}</h1>')
            continue
        if stripped.startswith('## ') and not stripped.startswith('### '):
            text = stripped[3:].strip()
            html_parts.append(f'<h2>{text}</h2>')
            continue
        if stripped.startswith('### ') and not stripped.startswith('#### '):
            text = stripped[4:].strip()
            html_parts.append(f'<h3>{text}</h3>')
            continue
        if stripped.startswith('#### '):
            text = stripped[5:].strip()
            html_parts.append(f'<h4>{text}</h4>')
            continue
        
        # Horizontal rule
        if stripped == '---':
            html_parts.append('<hr/>')
            continue
        
        # Blockquotes
        if stripped.startswith('>'):
            text = stripped.lstrip('>').strip()
            html_parts.append(f'<blockquote><em>{text}</em></blockquote>')
            continue
        
        # Lists
        if stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            text = stripped[2:].strip()
            text = format_bold(text)
            html_parts.append(f'<li>{text}</li>')
            continue
        elif in_list:
            html_parts.append('</ul>')
            in_list = False
        
        # Numbered lists
        if len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in '.):':
            text = stripped[2:].strip()
            text = format_bold(text)
            html_parts.append(f'<p class="list-item">{text}</p>')
            continue
        
        # Code blocks
        if stripped.startswith('```'):
            continue
        
        # Regular paragraph
        text = format_bold(stripped)
        html_parts.append(f'<p>{text}</p>')
    
    if in_list:
        html_parts.append('</ul>')
    if in_table:
        html_parts.append(build_table(table_rows))
    
    return '\n'.join(html_parts)

def format_bold(text):
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text

def build_table(rows):
    if not rows:
        return ''
    html = '<table>'
    for i, row in enumerate(rows):
        tag = 'th' if i == 0 else 'td'
        html += '<tr>'
        for cell in row:
            cell = format_bold(cell)
            html += f'<{tag}>{cell}</{tag}>'
        html += '</tr>'
    html += '</table>'
    return html

body_html = md_to_html(content)

# Full HTML with CSS styling
full_html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{
    size: A4;
    margin: 2.5cm 2cm 2.5cm 2cm;
    @top-center {{
        content: "ALPHA STACK — Institutional-Grade AI Trading System";
        font-size: 8pt;
        color: #666;
        font-family: 'Helvetica Neue', Arial, sans-serif;
    }}
    @bottom-center {{
        content: "Page " counter(page) " of " counter(pages);
        font-size: 8pt;
        color: #666;
        font-family: 'Helvetica Neue', Arial, sans-serif;
    }}
    @bottom-right {{
        content: "Confidential — July 2026";
        font-size: 7pt;
        color: #999;
        font-family: 'Helvetica Neue', Arial, sans-serif;
    }}
}}

@page :first {{
    @top-center {{ content: none; }}
    @bottom-center {{ content: none; }}
    @bottom-right {{ content: none; }}
}}

body {{
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: #1a1a1a;
    max-width: 100%;
}}

/* Cover Page */
.cover {{
    page-break-after: always;
    text-align: center;
    padding-top: 120px;
}}
.cover h1 {{
    font-size: 36pt;
    color: #0A1628;
    margin-bottom: 10px;
    letter-spacing: 3px;
}}
.cover .subtitle {{
    font-size: 18pt;
    color: #2D7FF9;
    margin-bottom: 30px;
    font-weight: 300;
}}
.cover .tagline {{
    font-size: 14pt;
    color: #555;
    font-style: italic;
    margin-bottom: 60px;
}}
.cover .meta {{
    font-size: 10pt;
    color: #888;
    line-height: 2;
}}
.cover .divider {{
    width: 100px;
    height: 3px;
    background: linear-gradient(to right, #2D7FF9, #00E676);
    margin: 40px auto;
}}

/* Table of Contents */
.toc {{
    page-break-after: always;
}}
.toc h2 {{
    color: #0A1628;
    border-bottom: 2px solid #2D7FF9;
    padding-bottom: 10px;
}}
.toc ul {{
    list-style: none;
    padding: 0;
}}
.toc li {{
    padding: 6px 0;
    border-bottom: 1px dotted #ddd;
    font-size: 10pt;
}}
.toc li strong {{
    color: #2D7FF9;
}}

/* Headings */
h1 {{
    font-size: 22pt;
    color: #0A1628;
    border-bottom: 3px solid #2D7FF9;
    padding-bottom: 8px;
    margin-top: 40px;
    margin-bottom: 20px;
    page-break-before: always;
}}
h1:first-of-type {{
    page-break-before: avoid;
}}
h2 {{
    font-size: 16pt;
    color: #0A1628;
    border-bottom: 1px solid #ddd;
    padding-bottom: 6px;
    margin-top: 30px;
    margin-bottom: 15px;
    page-break-before: always;
}}
h3 {{
    font-size: 13pt;
    color: #2D7FF9;
    margin-top: 25px;
    margin-bottom: 10px;
}}
h4 {{
    font-size: 11pt;
    color: #444;
    margin-top: 20px;
    margin-bottom: 8px;
}}

/* Paragraphs */
p {{
    margin-bottom: 10px;
    text-align: justify;
    hyphens: auto;
}}

/* Lists */
ul {{
    margin: 10px 0;
    padding-left: 25px;
}}
li {{
    margin-bottom: 5px;
    line-height: 1.5;
}}
.list-item {{
    margin-left: 20px;
    margin-bottom: 5px;
}}

/* Tables */
table {{
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
    font-size: 9pt;
    page-break-inside: avoid;
}}
th {{
    background-color: #0A1628;
    color: white;
    padding: 8px 10px;
    text-align: left;
    font-weight: 600;
    font-size: 8.5pt;
}}
td {{
    padding: 6px 10px;
    border-bottom: 1px solid #e0e0e0;
    vertical-align: top;
}}
tr:nth-child(even) {{
    background-color: #f8f9fa;
}}
tr:hover {{
    background-color: #e8f0fe;
}}

/* Blockquotes */
blockquote {{
    border-left: 4px solid #2D7FF9;
    padding: 10px 15px;
    margin: 15px 0;
    background-color: #f0f7ff;
    font-style: italic;
    color: #333;
}}

/* Code */
code {{
    background-color: #f4f4f4;
    padding: 2px 5px;
    border-radius: 3px;
    font-family: 'Courier New', monospace;
    font-size: 9pt;
    color: #d63384;
}}

/* Horizontal Rule */
hr {{
    border: none;
    height: 1px;
    background: linear-gradient(to right, #2D7FF9, #ddd, #2D7FF9);
    margin: 25px 0;
}}

/* Strong */
strong {{
    color: #0A1628;
}}

/* Emphasis */
em {{
    color: #555;
}}

/* Special boxes */
.finding {{
    background-color: #e8f5e9;
    border-left: 4px solid #00E676;
    padding: 10px 15px;
    margin: 15px 0;
}}
.warning {{
    background-color: #fff3e0;
    border-left: 4px solid #ff9800;
    padding: 10px 15px;
    margin: 15px 0;
}}
.critical {{
    background-color: #ffebee;
    border-left: 4px solid #f44336;
    padding: 10px 15px;
    margin: 15px 0;
}}
</style>
</head>
<body>

<!-- Cover Page -->
<div class="cover">
    <h1>ALPHA STACK</h1>
    <div class="subtitle">Institutional-Grade AI Trading System</div>
    <div class="divider"></div>
    <div class="tagline">Stack the Alpha. Beat the Market.</div>
    <div class="meta">
        <strong>Complete Research & Architecture Compilation</strong><br/>
        54 Research Reports | 31 Architecture Documents<br/><br/>
        Prepared for: Valentine Owuor<br/>
        BSc Economics & Statistics<br/><br/>
        Date: July 2026<br/>
        Version: 1.0<br/>
        Classification: Confidential — Internal Use Only
    </div>
</div>

<!-- Executive Summary Section -->
<div class="toc">
<h2>Table of Contents</h2>
<ul>
    <li><strong>PART 1:</strong> Market & Business Research (8 reports)</li>
    <li><strong>PART 2:</strong> Strategy Research — Alpha Strategy Enhancement (10 reports)</li>
    <li><strong>PART 3:</strong> Technology Research (8 reports)</li>
    <li><strong>PART 4:</strong> Platform Research (8 reports)</li>
    <li><strong>PART 5:</strong> Academic & Curriculum Integration (14 reports)</li>
    <li><strong>PART 6:</strong> Compliance & Branding (6 reports)</li>
</ul>
</div>

<!-- Main Content -->
{body_html}

</body>
</html>'''

# Generate PDF
print("Generating PDF...")
HTML(string=full_html).write_pdf('AlphaStack_Complete_Report.pdf')
print("PDF generated successfully!")

# Check file size
size = os.path.getsize('AlphaStack_Complete_Report.pdf')
print(f"File size: {size / 1024:.0f} KB ({size / (1024*1024):.1f} MB)")
