#!/usr/bin/env python3
"""
Generate PNG icons from SVG for PWA manifest.
This script creates the required icon sizes for the PWA.
"""

import os
import subprocess
from pathlib import Path


def create_placeholder_png(size, output_path):
    """Create a placeholder PNG icon using Python PIL."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create image with gradient background
        img = Image.new('RGBA', (size, size), (99, 102, 241, 255))
        draw = ImageDraw.Draw(img)
        
        # Draw a simple music note
        center_x, center_y = size // 2, size // 2
        
        # Note stem
        stem_width = max(2, size // 64)
        stem_height = size // 3
        stem_x = center_x - stem_width // 2
        stem_y = center_y - stem_height // 2
        draw.rectangle([stem_x, stem_y, stem_x + stem_width, stem_y + stem_height], fill='white')
        
        # Note head
        head_size = size // 8
        head_x = center_x - head_size
        head_y = center_y + stem_height // 4
        draw.ellipse([head_x, head_y, head_x + head_size * 2, head_y + head_size], fill='white')
        
        # Musical staff lines
        staff_width = size // 2
        staff_x = center_x - staff_width // 2
        line_thickness = max(1, size // 256)
        
        for i in range(5):
            y = center_y - size // 8 + i * (size // 32)
            draw.rectangle([staff_x, y, staff_x + staff_width, y + line_thickness], 
                         fill=(255, 255, 255, 150))
        
        # Save the image
        img.save(output_path, 'PNG')
        print(f"Created {output_path} ({size}x{size})")
        
    except ImportError:
        print("PIL not available, creating simple colored square")
        # Fallback: create a simple colored square
        img = Image.new('RGB', (size, size), (99, 102, 241))
        img.save(output_path, 'PNG')


def generate_icons():
    """Generate all required icon sizes."""
    base_dir = Path(__file__).parent.parent
    images_dir = base_dir / "festival_playlist_generator" / "web" / "static" / "images"
    
    # Ensure images directory exists
    images_dir.mkdir(parents=True, exist_ok=True)
    
    # Icon sizes needed for PWA
    icon_sizes = [192, 512]
    shortcut_sizes = [96]
    
    # Try to use PIL for better quality icons
    try:
        from PIL import Image
        pil_available = True
    except ImportError:
        pil_available = False
        print("PIL not available. Install with: pip install Pillow")
    
    # Generate main app icons
    for size in icon_sizes:
        output_path = images_dir / f"icon-{size}.png"
        if pil_available:
            create_placeholder_png(size, output_path)
        else:
            # Create a very basic fallback
            with open(output_path, 'wb') as f:
                # This is a minimal 1x1 PNG - not ideal but functional
                f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x12IDATx\x9cc```bPPP\x00\x02\xac\xea\x05\x1b\x00\x00\x00\x00IEND\xaeB`\x82')
    
    # Generate shortcut icons (simplified versions)
    shortcut_names = ['festivals', 'playlists', 'search', 'streaming']
    colors = [(34, 197, 94), (239, 68, 68), (59, 130, 246), (168, 85, 247)]  # Green, Red, Blue, Purple
    
    if pil_available:
        from PIL import ImageDraw
        for i, (name, color) in enumerate(zip(shortcut_names, colors)):
            output_path = images_dir / f"shortcut-{name}.png"
            
            # Create colored icon for each shortcut
            img = Image.new('RGBA', (96, 96), (*color, 255))
            draw = ImageDraw.Draw(img)
            
            # Add simple icon based on type
            if name == 'festivals':
                # Triangle for tent
                draw.polygon([(30, 60), (66, 60), (48, 30)], fill='white')
                draw.rectangle([46, 60, 50, 70], fill='white')
            elif name == 'playlists':
                # List lines
                for j in range(4):
                    y = 25 + j * 12
                    draw.rectangle([20, y, 76, y + 3], fill='white')
            elif name == 'search':
                # Magnifying glass
                draw.ellipse([25, 25, 55, 55], outline='white', width=4)
                draw.line([(50, 50), (70, 70)], fill='white', width=4)
            elif name == 'streaming':
                # Play button
                draw.polygon([(35, 25), (35, 71), (65, 48)], fill='white')
            
            img.save(output_path, 'PNG')
            print(f"Created {output_path} (96x96)")
    
    # Create placeholder screenshots
    screenshot_paths = [
        ('screenshot-mobile.png', 390, 844),
        ('screenshot-desktop.png', 1280, 720)
    ]
    
    if pil_available:
        from PIL import ImageDraw
        for filename, width, height in screenshot_paths:
            output_path = images_dir / filename
            
            # Create a simple mockup screenshot
            img = Image.new('RGB', (width, height), (249, 250, 251))
            draw = ImageDraw.Draw(img)
            
            # Header
            header_height = height // 10
            draw.rectangle([0, 0, width, header_height], fill=(99, 102, 241))
            
            # Title
            title_y = header_height // 3
            draw.rectangle([width // 20, title_y, width // 2, title_y + header_height // 3], 
                         fill=(255, 255, 255))
            
            # Content area
            content_y = header_height + 20
            for i in range(3):
                item_y = content_y + i * (height // 8)
                draw.rectangle([width // 20, item_y, width - width // 20, item_y + height // 12], 
                             fill=(229, 231, 235))
            
            img.save(output_path, 'PNG')
            print(f"Created {output_path} ({width}x{height})")
    
    # Generate placeholder image
    placeholder_path = images_dir / "placeholder.png"
    if pil_available:
        # Create a simple placeholder
        img = Image.new('RGB', (300, 200), (229, 231, 235))
        draw = ImageDraw.Draw(img)
        
        # Add placeholder text
        text = "Loading..."
        bbox = draw.textbbox((0, 0), text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (300 - text_width) // 2
        y = (200 - text_height) // 2
        draw.text((x, y), text, fill=(156, 163, 175))
        
        img.save(placeholder_path, 'PNG')
        print(f"Created {placeholder_path} (300x200)")
    
    print("\nIcon generation complete!")
    print("Note: For production, consider using professional icons and actual screenshots.")


if __name__ == "__main__":
    generate_icons()