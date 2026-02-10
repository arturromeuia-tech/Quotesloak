import os
import csv
import io
import zipfile
import base64
import uuid
import shutil
from flask import Flask, render_template, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# --- DIRECTORY CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')
TEMP_FOLDER = os.path.join(BASE_DIR, 'temp')
MODELS_FOLDER = os.path.join(BASE_DIR, 'models')

for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, TEMP_FOLDER, MODELS_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# --- CANVAS AND BRANDING SPECIFICATIONS ---
CANVAS_WIDTH = 1080  # Canvas Width
CANVAS_HEIGHT = 1350 # Canvas Height (4:5 Ratio)
GOLD_COLOR = "#c5a55f" # Soft Gold Accent
TEXT_COLOR = "#FFFFFF" # Main Text Color (White)

# --- STRICT TEXT GEOMETRY ---
POST_FONT_SIZE = 42        # Font Size
POST_FIXED_MAX_WIDTH = 590 # Max Text Box Width
POST_FIXED_LINE_HEIGHT = 70 # Line Spacing

# --- VERTICAL POSITIONING (Y-AXIS) ---
# Fixed position removed. Now dynamic.
CANVAS_CENTER_Y = 1350 // 2
BLOCK_GAP = 50
Y_ANCHOR_OFFSET = 35

# --- HORIZONTAL CENTERING LOGIC (X-AXIS) ---
# Dynamically calculated to center the 590px box
FIXED_LEFT_X = (CANVAS_WIDTH - POST_FIXED_MAX_WIDTH) // 2 
# Result: 245px from left edge

# --- CAROUSEL CONFIGURATION (INDEPENDENT) ---
CAROUSEL_FONT_SIZE = 42
CAROUSEL_FIXED_MAX_WIDTH = 590
CAROUSEL_FIXED_LINE_HEIGHT = 70
# Calculated independently for Carousels
CAROUSEL_LEFT_X = (CANVAS_WIDTH - CAROUSEL_FIXED_MAX_WIDTH) // 2 


def get_safe_font(font_path, font_size):
    if not os.path.exists(font_path):
        # Try looking in static or current directory
        potential_path = os.path.join(BASE_DIR, "static", font_path)
        if os.path.exists(potential_path):
            font_path = potential_path
        else:
             import glob
             fonts = glob.glob(os.path.join(BASE_DIR, "*.otf")) + glob.glob(os.path.join(BASE_DIR, "*.ttf"))
             font_path = fonts[0] if fonts else "arial.ttf"

    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()
    return font

def wrap_text(text, font, max_width, draw):
    lines = []
    paragraphs = text.split('\n')
    for paragraph in paragraphs:
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current_line = words[0]
        for word in words[1:]:
            try:
                test_line = current_line + " " + word
                bbox = draw.textbbox((0, 0), test_line, font=font)
                text_width = bbox[2] - bbox[0]
                if text_width <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            except:
                 lines.append(current_line)
                 current_line = word
        lines.append(current_line)
    return lines

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html', app_version=os.environ.get('APP_VERSION', 'v2'))

@app.route('/generate', methods=['POST'])
def generate_posts():
    try:
        # "Aesthetic" Configuration
        font_path = os.path.join(BASE_DIR, "NeueMontreal-Regular.otf")
        base_img_path = os.path.join(BASE_DIR, "Post LOAK.png")
        
        task_id = str(uuid.uuid4())
        task_dir = os.path.join(TEMP_FOLDER, task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        process_csv_path = os.path.join(task_dir, 'data.csv')
        process_img_path = os.path.join(task_dir, 'template.png')

        # 1. Get files
        if 'csv_file' in request.files and request.files['csv_file'].filename:
            request.files['csv_file'].save(process_csv_path)
        else:
            # Local fallback for development
            local_csv = os.path.join(BASE_DIR, "quotes_150_completo.csv")
            if os.path.exists(local_csv):
                 shutil.copy(local_csv, process_csv_path)
            else:
                 return jsonify({'error': 'CSV not found'}), 400

        if 'image_file' in request.files and request.files['image_file'].filename:
             request.files['image_file'].save(process_img_path)
        elif os.path.exists(base_img_path):
             shutil.copy(base_img_path, process_img_path)
        else:
             return jsonify({'error': 'Base image not found'}), 400
        
        # 2. Process
        generated_images = []
        previews = []
        
        base_img = Image.open(process_img_path).convert("RGBA")
        img_width, img_height = base_img.size
        
        font = get_safe_font(font_path, POST_FONT_SIZE)
        

        
        with open(process_csv_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            # Deduce dialect
            content = f.read()
            f.seek(0)
            try:
                if ';' in content and ',' not in content:
                    dialect = 'excel-tab' 
                    delimiter = ';'
                else:
                    dialect = csv.Sniffer().sniff(content[:2048])
                    delimiter = dialect.delimiter
            except:
                delimiter = ','
            
            f.seek(0)
            reader = csv.DictReader(f, delimiter=delimiter)
            
            count = 0
            for row in reader:
                try:
                    count += 1
                    if count > 300: break # Safety limit
                    
                    # Normalize keys
                    keys = list(row.keys())
                    def get_val(keys, target):
                        for k in keys:
                            if k and k.lower() == target:
                                return row[k]
                        return ''

                    linea1 = get_val(keys, 'texto_linea1') or get_val(keys, 'linea1') or (list(row.values())[0] if row else '')
                    linea2 = get_val(keys, 'texto_linea2') or get_val(keys, 'linea2') or ''
                    
                    if not str(linea1).strip(): continue

                    img = base_img.copy()
                    draw = ImageDraw.Draw(img)
                    
                    # --- DYNAMIC HEIGHT CALCULATION (POSTS) ---
                    lines1 = wrap_text(str(linea1).strip(), font, POST_FIXED_MAX_WIDTH, draw)
                    h1 = len(lines1) * POST_FIXED_LINE_HEIGHT
                    
                    lines2 = []
                    h2 = 0
                    gap = 0
                    
                    if linea2 and str(linea2).strip():
                        lines2 = wrap_text(str(linea2).strip(), font, POST_FIXED_MAX_WIDTH, draw)
                        h2 = len(lines2) * POST_FIXED_LINE_HEIGHT
                        gap = BLOCK_GAP
                    
                    total_height = h1 + gap + h2
                    # Y_Start = Canvas_Center - (Total_Height / 2) + 35
                    start_y = CANVAS_CENTER_Y - (total_height // 2) + Y_ANCHOR_OFFSET
                    
                    # --- DRAW (POSTS) ---
                    current_y = start_y
                    
                    # Block 1
                    for line in lines1:
                        draw.text((FIXED_LEFT_X, current_y), line, font=font, anchor='lm', fill=TEXT_COLOR)
                        current_y += POST_FIXED_LINE_HEIGHT
                    
                    if lines2:
                        current_y += gap
                        # Block 2
                        for line in lines2:
                             draw.text((FIXED_LEFT_X, current_y), line, font=font, anchor='lm', fill=TEXT_COLOR)
                             current_y += POST_FIXED_LINE_HEIGHT
                    
                    out_name = f"Post_LOAK_{count}.png"
                    temp_out_path = os.path.join(task_dir, out_name)
                    img.save(temp_out_path)
                    generated_images.append(temp_out_path)
                    
                    if len(previews) < 3:
                        thumb = img.copy()
                        thumb.thumbnail((300, 300))
                        buffered = io.BytesIO()
                        thumb.save(buffered, format="PNG")
                        b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                        previews.append(f"data:image/png;base64,{b64}")

                except Exception as e:
                    print(f"Error row {count}: {e}")
                    continue

        # 3. ZIP Result
        zip_filename = f"Posts_LOAK_{task_id[:8]}.zip"
        zip_path = os.path.join(OUTPUT_FOLDER, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for img_file in generated_images:
                zipf.write(img_file, os.path.basename(img_file))
        
        shutil.rmtree(task_dir)
        
        return jsonify({
            'success': True,
            'count': len(generated_images),
            'download_url': f"/download/{zip_filename}",
            'previews': previews
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate_carousels', methods=['POST'])
def generate_carousels():
    try:
        font_path = os.path.join(BASE_DIR, "NeueMontreal-Regular.otf")
        base_img_path = os.path.join(BASE_DIR, "Post LOAK.png")
        
        task_id = str(uuid.uuid4())
        task_dir = os.path.join(TEMP_FOLDER, task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        process_csv_path = os.path.join(task_dir, 'data_carousel.csv')
        process_img_path = os.path.join(task_dir, 'template.png')

        # 1. Inputs
        if 'carousel_csv' in request.files and request.files['carousel_csv'].filename:
            request.files['carousel_csv'].save(process_csv_path)
        else:
             # Try fallback
             local_csv = os.path.join(BASE_DIR, "carruseles_lawofattractionkey (1).csv")
             if os.path.exists(local_csv):
                 shutil.copy(local_csv, process_csv_path)
             else:
                 return jsonify({'error': 'Carousel CSV not found'}), 400

        if 'image_file' in request.files and request.files['image_file'].filename:
             request.files['image_file'].save(process_img_path)
        elif os.path.exists(base_img_path):
             shutil.copy(base_img_path, process_img_path)
        else:
             return jsonify({'error': 'Base image not found'}), 400

        # 2. Config & Load
        base_img = Image.open(process_img_path).convert("RGBA")
        img_width, img_height = base_img.size
        # Use Carousel Constants
        font = get_safe_font(font_path, CAROUSEL_FONT_SIZE)


        # 3. Grouping Logic
        carrousels = {}
        with open(process_csv_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            # Deduce delimiters
            content = f.read()
            f.seek(0)
            try:
                if ';' in content and ',' not in content: delimiter = ';'
                else:
                    dialect = csv.Sniffer().sniff(content[:2048])
                    delimiter = dialect.delimiter
            except: delimiter = ','
            
            f.seek(0)
            reader = csv.DictReader(f, delimiter=delimiter)
            
            for row in reader:
                c_id = None
                # Strict search for carrusel_id
                for k in row.keys():
                    if k and k.strip().lower() == 'carrusel_id':
                        c_id = str(row[k]).strip()
                        break
                
                if not c_id: continue
                if c_id not in carrousels: carrousels[c_id] = []
                carrousels[c_id].append(row)

        output_zips_dir = os.path.join(task_dir, "outputs")
        os.makedirs(output_zips_dir, exist_ok=True)
        
        carousel_zip_paths = []
        previews = []
        total_images = 0

        # Sort carousels numeric if possible
        sorted_ids = sorted(carrousels.keys(), key=lambda x: int(x) if x.isdigit() else x)

        for c_id in sorted_ids:
            slides = carrousels[c_id]
            c_id_str = str(c_id).zfill(2)
            c_temp_dir = os.path.join(task_dir, f"c_{c_id_str}")
            os.makedirs(c_temp_dir, exist_ok=True)
            
            # Sort slides
            def get_sn(s):
                for k in s.keys():
                    if k and k.strip().lower() == 'slide_numero':
                        val = str(s[k]).strip()
                        return int(val) if val.isdigit() else 0
                return 0

            slides.sort(key=get_sn)

            for slide in slides:
                # Normalize keys strictly
                keys = list(slide.keys())
                
                def get_val_strict(keys, target):
                    for k in keys:
                        if k and k.strip().lower() == target:
                            return slide[k]
                    return ''

                # Strict mapping per instructions
                linea1 = get_val_strict(keys, 'texto_linea1')
                linea2 = get_val_strict(keys, 'texto_linea2')
                
                # Rule of Gold: Normalization
                if linea1: linea1 = str(linea1).strip()
                if linea2: linea2 = str(linea2).strip()
                
                img = base_img.copy()
                draw = ImageDraw.Draw(img)
                
                # --- DYNAMIC HEIGHT CALCULATION (CAROUSELS) ---
                lines1 = []
                h1 = 0
                if linea1:
                    lines1 = wrap_text(linea1, font, CAROUSEL_FIXED_MAX_WIDTH, draw)
                    h1 = len(lines1) * CAROUSEL_FIXED_LINE_HEIGHT
                
                lines2 = []
                h2 = 0
                gap = 0
                if linea2:
                    lines2 = wrap_text(linea2, font, CAROUSEL_FIXED_MAX_WIDTH, draw)
                    h2 = len(lines2) * CAROUSEL_FIXED_LINE_HEIGHT
                    # Only add gap if we have both block 1 AND block 2
                    gap = BLOCK_GAP if (lines1 and lines2) else 0
                
                total_height = h1 + gap + h2
                start_y = CANVAS_CENTER_Y - (total_height // 2) + Y_ANCHOR_OFFSET

                # --- DRAW (CAROUSELS) ---
                current_y = start_y

                # Block 1
                for line in lines1:
                    draw.text((CAROUSEL_LEFT_X, current_y), line, font=font, anchor='lm', fill=TEXT_COLOR)
                    current_y += CAROUSEL_FIXED_LINE_HEIGHT
                
                if lines2:
                    current_y += gap
                    # Block 2
                    for line in lines2:
                        draw.text((CAROUSEL_LEFT_X, current_y), line, font=font, anchor='lm', fill=TEXT_COLOR)
                        current_y += CAROUSEL_FIXED_LINE_HEIGHT

                s_num = get_sn(slide)
                out_name = f"slide_{s_num}.png"
                img.save(os.path.join(c_temp_dir, out_name))
                total_images += 1

                if len(previews) < 3 and s_num == 1:
                    thumb = img.copy()
                    thumb.thumbnail((300, 300))
                    buffered = io.BytesIO()
                    thumb.save(buffered, format="PNG")
                    b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                    previews.append(f"data:image/png;base64,{b64}")

            # ZIP individual
            zip_name = f"carousel_{c_id_str}.zip"
            zip_path = os.path.join(output_zips_dir, zip_name)
            with zipfile.ZipFile(zip_path, 'w') as zf:
                for f in os.listdir(c_temp_dir):
                    zf.write(os.path.join(c_temp_dir, f), f)
            carousel_zip_paths.append(zip_path)

        # Master ZIP
        master_zip_name = f"Carrousels_LOAK_{task_id[:8]}.zip"
        master_zip_path = os.path.join(OUTPUT_FOLDER, master_zip_name)
        
        with zipfile.ZipFile(master_zip_path, 'w') as zf:
            for zp in carousel_zip_paths:
                zf.write(zp, os.path.basename(zp))
        
        shutil.rmtree(task_dir)
        
        return jsonify({
            'success': True,
            'count': total_images,
            'carousels_count': len(carousel_zip_paths),
            'download_url': f"/download/{master_zip_name}",
            'previews': previews
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename), as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, host='0.0.0.0', port=port, threaded=True)
