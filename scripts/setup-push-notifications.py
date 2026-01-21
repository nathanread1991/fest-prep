#!/usr/bin/env python3
"""
Setup script for push notifications.
Generates VAPID keys and updates environment configuration.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from festival_playlist_generator.services.push_notifications import PushNotificationService


def setup_push_notifications():
    """Set up push notifications by generating VAPID keys."""
    print("Setting up push notifications...")
    
    # Generate VAPID keys
    print("Generating VAPID keys...")
    keys = PushNotificationService.generate_vapid_keys()
    
    print(f"Private Key: {keys['private_key']}")
    print(f"Public Key: {keys['public_key']}")
    
    # Check if .env file exists
    env_file = project_root / ".env"
    env_example_file = project_root / ".env.example"
    
    # Read existing .env or create from example
    env_content = ""
    if env_file.exists():
        with open(env_file, 'r') as f:
            env_content = f.read()
    elif env_example_file.exists():
        with open(env_example_file, 'r') as f:
            env_content = f.read()
    
    # Update or add VAPID keys
    lines = env_content.split('\n')
    updated_lines = []
    vapid_private_found = False
    vapid_public_found = False
    vapid_email_found = False
    
    for line in lines:
        if line.startswith('VAPID_PRIVATE_KEY='):
            updated_lines.append(f'VAPID_PRIVATE_KEY={keys["private_key"]}')
            vapid_private_found = True
        elif line.startswith('VAPID_PUBLIC_KEY='):
            updated_lines.append(f'VAPID_PUBLIC_KEY={keys["public_key"]}')
            vapid_public_found = True
        elif line.startswith('VAPID_EMAIL='):
            vapid_email_found = True
            updated_lines.append(line)
        else:
            updated_lines.append(line)
    
    # Add missing VAPID configuration
    if not vapid_private_found:
        updated_lines.append(f'VAPID_PRIVATE_KEY={keys["private_key"]}')
    if not vapid_public_found:
        updated_lines.append(f'VAPID_PUBLIC_KEY={keys["public_key"]}')
    if not vapid_email_found:
        updated_lines.append('VAPID_EMAIL=admin@festivalplaylists.com')
    
    # Write updated .env file
    with open(env_file, 'w') as f:
        f.write('\n'.join(updated_lines))
    
    print(f"\n✅ VAPID keys have been generated and saved to {env_file}")
    print("\n📝 Next steps:")
    print("1. Restart your application to load the new environment variables")
    print("2. Test push notifications using the notification controls in the web interface")
    print("3. For production, consider using a more secure email address for VAPID_EMAIL")
    
    print("\n🔧 Manual setup (if needed):")
    print("Add these lines to your .env file:")
    print(f"VAPID_PRIVATE_KEY={keys['private_key']}")
    print(f"VAPID_PUBLIC_KEY={keys['public_key']}")
    print("VAPID_EMAIL=admin@festivalplaylists.com")


if __name__ == "__main__":
    setup_push_notifications()