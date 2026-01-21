#!/usr/bin/env python3
"""
Build script for minifying CSS and JavaScript assets.
This script provides basic minification for production builds.
"""

import os
import re
import json
import hashlib
from pathlib import Path


def minify_css(css_content):
    """Basic CSS minification."""
    # Remove comments
    css_content = re.sub(r'/\*.*?\*/', '', css_content, flags=re.DOTALL)
    
    # Remove unnecessary whitespace
    css_content = re.sub(r'\s+', ' ', css_content)
    
    # Remove whitespace around specific characters
    css_content = re.sub(r'\s*([{}:;,>+~])\s*', r'\1', css_content)
    
    # Remove trailing semicolons before closing braces
    css_content = re.sub(r';\s*}', '}', css_content)
    
    # Remove leading/trailing whitespace
    css_content = css_content.strip()
    
    return css_content


def minify_js(js_content):
    """Basic JavaScript minification."""
    # Remove single-line comments (but preserve URLs)
    js_content = re.sub(r'(?<!:)//.*$', '', js_content, flags=re.MULTILINE)
    
    # Remove multi-line comments
    js_content = re.sub(r'/\*.*?\*/', '', js_content, flags=re.DOTALL)
    
    # Remove unnecessary whitespace (preserve strings)
    in_string = False
    string_char = None
    result = []
    i = 0
    
    while i < len(js_content):
        char = js_content[i]
        
        if not in_string and char in ['"', "'"]:
            in_string = True
            string_char = char
            result.append(char)
        elif in_string and char == string_char and js_content[i-1] != '\\':
            in_string = False
            string_char = None
            result.append(char)
        elif in_string:
            result.append(char)
        elif char.isspace():
            # Only keep necessary whitespace
            if (i > 0 and i < len(js_content) - 1 and
                js_content[i-1].isalnum() and js_content[i+1].isalnum()):
                result.append(' ')
        else:
            result.append(char)
        
        i += 1
    
    return ''.join(result)


def generate_file_hash(content):
    """Generate MD5 hash for cache busting."""
    return hashlib.md5(content.encode()).hexdigest()[:8]


def process_assets():
    """Process and minify CSS and JavaScript assets."""
    base_dir = Path(__file__).parent.parent
    static_dir = base_dir / "festival_playlist_generator" / "web" / "static"
    
    # Asset manifest for cache busting
    manifest = {}
    
    # Process CSS files
    css_dir = static_dir / "css"
    if css_dir.exists():
        for css_file in css_dir.glob("*.css"):
            if css_file.name.endswith(".min.css"):
                continue
                
            print(f"Processing CSS: {css_file.name}")
            
            with open(css_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Minify CSS
            minified = minify_css(content)
            
            # Generate hash for cache busting
            file_hash = generate_file_hash(minified)
            
            # Create minified file
            min_file = css_file.parent / f"{css_file.stem}.min.css"
            with open(min_file, 'w', encoding='utf-8') as f:
                f.write(minified)
            
            # Create versioned file for cache busting
            versioned_file = css_file.parent / f"{css_file.stem}.{file_hash}.min.css"
            with open(versioned_file, 'w', encoding='utf-8') as f:
                f.write(minified)
            
            # Update manifest
            manifest[f"css/{css_file.name}"] = f"css/{css_file.stem}.{file_hash}.min.css"
            
            print(f"  Original: {len(content)} bytes")
            print(f"  Minified: {len(minified)} bytes")
            print(f"  Savings: {len(content) - len(minified)} bytes ({((len(content) - len(minified)) / len(content) * 100):.1f}%)")
    
    # Process JavaScript files
    js_dir = static_dir / "js"
    if js_dir.exists():
        for js_file in js_dir.glob("*.js"):
            if js_file.name.endswith(".min.js") or js_file.name == "sw.js":
                continue
                
            print(f"Processing JS: {js_file.name}")
            
            with open(js_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Minify JavaScript
            minified = minify_js(content)
            
            # Generate hash for cache busting
            file_hash = generate_file_hash(minified)
            
            # Create minified file
            min_file = js_file.parent / f"{js_file.stem}.min.js"
            with open(min_file, 'w', encoding='utf-8') as f:
                f.write(minified)
            
            # Create versioned file for cache busting
            versioned_file = js_file.parent / f"{js_file.stem}.{file_hash}.min.js"
            with open(versioned_file, 'w', encoding='utf-8') as f:
                f.write(minified)
            
            # Update manifest
            manifest[f"js/{js_file.name}"] = f"js/{js_file.stem}.{file_hash}.min.js"
            
            print(f"  Original: {len(content)} bytes")
            print(f"  Minified: {len(minified)} bytes")
            print(f"  Savings: {len(content) - len(minified)} bytes ({((len(content) - len(minified)) / len(content) * 100):.1f}%)")
    
    # Save asset manifest
    manifest_file = static_dir / "manifest-assets.json"
    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\nAsset manifest saved to: {manifest_file}")
    print("Build complete!")


if __name__ == "__main__":
    process_assets()