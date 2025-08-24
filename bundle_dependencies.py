#!/usr/bin/env python3
"""
Dependency Bundler for PLM Log Analyzer
This script downloads all required dependencies and bundles them locally for offline use.
Run this script once on a machine with internet access, then distribute the entire folder.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def create_directories():
    """Create necessary directories for dependency bundling"""
    dirs = [
        'libs',
        'libs/flask',
        'libs/werkzeug', 
        'libs/jinja2',
        'libs/markupsafe',
        'libs/itsdangerous',
        'libs/click',
        'libs/blinker',
        'libs/click',
        'libs/typing_extensions',
        'libs/importlib_metadata',
        'libs/zipp',
        'libs/packaging',
        'libs/pyparsing',
        'libs/setuptools',
        'libs/wheel',
        'libs/pip',
        'libs/requests',
        'libs/urllib3',
        'libs/certifi',
        'libs/charset_normalizer',
        'libs/idna',
        'libs/colorama',
        'libs/distlib',
        'libs/filelock',
        'libs/platformdirs',
        'libs/packaging',
        'libs/pyparsing',
        'libs/setuptools',
        'libs/wheel',
        'libs/pip',
        'libs/requests',
        'libs/urllib3',
        'libs/certifi',
        'libs/charset_normalizer',
        'libs/idna',
        'libs/colorama',
        'libs/distlib',
        'libs/filelock',
        'libs/platformdirs'
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"📁 Created directory: {dir_path}")

def download_dependencies():
    """Download all required dependencies"""
    dependencies = [
        'flask==2.3.3',
        'werkzeug==2.3.7',
        'jinja2==3.1.2',
        'markupsafe==2.1.3',
        'itsdangerous==2.1.2',
        'click==8.1.7',
        'blinker==1.6.3',
        'typing_extensions==4.7.1',
        'importlib_metadata==6.7.0',
        'zipp==3.16.2',
        'packaging==23.1',
        'pyparsing==3.0.9',
        'setuptools==68.0.0',
        'wheel==0.41.2',
        'pip==23.2.1'
    ]
    
    for dep in dependencies:
        print(f"📦 Downloading {dep}...")
        if not run_command(f"pip download {dep} -d libs/", f"Download {dep}"):
            print(f"⚠️  Warning: Failed to download {dep}")
            continue

def create_offline_installer():
    """Create an offline installer script"""
    installer_content = '''#!/usr/bin/env python3
"""
Offline Dependency Installer for PLM Log Analyzer
Run this script to install all dependencies from local files.
"""

import os
import sys
import subprocess
from pathlib import Path

def install_from_local():
    """Install dependencies from local libs folder"""
    libs_dir = Path("libs")
    
    if not libs_dir.exists():
        print("❌ libs folder not found!")
        return False
    
    # Find all wheel files
    wheel_files = list(libs_dir.glob("*.whl"))
    
    if not wheel_files:
        print("❌ No wheel files found in libs folder!")
        return False
    
    print(f"📦 Found {len(wheel_files)} packages to install...")
    
    for wheel_file in wheel_files:
        print(f"🔄 Installing {wheel_file.name}...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", str(wheel_file)], 
                         check=True, capture_output=True)
            print(f"✅ Installed {wheel_file.name}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {wheel_file.name}: {e}")
            return False
    
    return True

if __name__ == "__main__":
    print("🚀 PLM Log Analyzer - Offline Dependency Installer")
    print("=" * 50)
    
    if install_from_local():
        print("\\n🎉 All dependencies installed successfully!")
        print("You can now run: python app.py")
    else:
        print("\\n❌ Installation failed. Please check the errors above.")
        sys.exit(1)
'''
    
    with open('install_dependencies.py', 'w') as f:
        f.write(installer_content)
    
    print("✅ Created offline installer: install_dependencies.py")

def create_requirements_local():
    """Create a local requirements file"""
    requirements_content = '''# Local Dependencies for PLM Log Analyzer
# All packages are bundled in the libs/ folder
# Run install_dependencies.py to install them

# Core Flask dependencies
flask==2.3.3
werkzeug==2.3.7
jinja2==3.1.2
markupsafe==2.1.3
itsdangerous==2.1.2
click==8.1.7
blinker==1.6.3

# Additional dependencies
typing_extensions==4.7.1
importlib_metadata==6.7.0
zipp==3.16.2
packaging==23.1
pyparsing==3.0.9
setuptools==68.0.0
wheel==0.41.2
pip==23.2.1

# Note: This file is for reference only.
# Actual packages are in the libs/ folder.
# Use install_dependencies.py to install them.
'''
    
    with open('requirements_local.txt', 'w') as f:
        f.write(requirements_content)
    
    print("✅ Created local requirements file: requirements_local.txt")

def create_readme():
    """Create a comprehensive README for team members"""
    readme_content = '''# PLM Log Analyzer - Samsung Engineering Team

## 🚀 Quick Start (Offline Installation)

### Prerequisites
- Python 3.7 or higher installed
- No internet connection required after setup

### Installation Steps
1. **Extract the project folder** to your local machine
2. **Open command prompt/terminal** in the project folder
3. **Install dependencies** (one-time setup):
   ```bash
   python install_dependencies.py
   ```
4. **Launch the application**:
   ```bash
   python app.py
   ```
5. **Open browser** and go to: `http://localhost:5000`

## 📁 Project Structure
```
PlmAnalyzer/
├── app.py                          # Main Flask application
├── install_dependencies.py         # Offline dependency installer
├── requirements_local.txt          # Local requirements reference
├── libs/                          # All bundled dependencies
├── templates/                     # HTML templates
│   ├── index.html                # Main upload form
│   └── results.html              # Results display
├── uploads/                      # Uploaded log files (auto-created)
└── README.md                     # This file
```

## 🔧 Features
- **Issue Type Selection**: Choose from predefined Samsung device issue categories
- **Package Filtering**: Filter logs by specific app package names
- **Custom Analysis**: Dedicated methods for each issue type
- **Large File Support**: Handles Samsung log files up to 500MB
- **Offline Operation**: Works completely without internet connection

## 🎯 Issue Categories Supported
- **Audio Issues**: Noise, multiple output, not working
- **Camera Issues**: Launch failures, rotation, crashes
- **App Crashes**: Force stops, crashes, ANRs, device reboots
- **UI Issues**: Layout problems, UI crashes
- **Network Issues**: Connection problems, HTTP errors
- **Memory Issues**: Out of memory errors
- **Multimedia Issues**: Video playback, streaming, codec issues
- **Bluetooth Issues**: Connection, audio, pairing problems
- **App Installation**: Install failures, update issues, permissions
- **Battery Issues**: Drain problems, charging issues
- **Storage Issues**: Space problems, file corruption, SD card
- **Security Issues**: Permission denied, authentication, root detection

## 🛠️ Customization for Team Members
Each issue type has dedicated analysis methods in `app.py`:
- `analyze_audio_issues()`
- `analyze_camera_issues()`
- `analyze_app_crashes()`
- `analyze_ui_issues()`
- `analyze_network_issues()`
- And more...

Add your custom log extraction logic in these methods.

## 📊 Usage Example
1. Select **Main Issue Type**: "App Crashes"
2. Select **Sub-Issue Type**: "Device Reboot"
3. Enter **Package Name** (optional): "com.samsung.android.app"
4. Upload your Samsung log file
5. View analysis results with extracted relevant logs

## 🔍 Troubleshooting
- **Port 5000 in use**: Change port in `app.py` line: `app.run(debug=True, host='0.0.0.0', port=5001)`
- **Dependencies not found**: Run `python install_dependencies.py` again
- **Large files not working**: Check file size limit in `app.py` (currently 500MB)

## 👥 Team Development
- All code is in `app.py` - modify analysis methods as needed
- Templates in `templates/` folder for UI changes
- Add new issue types in the `issue_categories` dictionary
- Test with your Samsung device logs

## 📞 Support
For issues or questions, contact your team lead or refer to the code comments in `app.py`.

---
**Samsung Engineering Team - PLM Log Analyzer v1.0**
'''
    
    with open('README.md', 'w') as f:
        f.write(readme_content)
    
    print("✅ Created comprehensive README: README.md")

def main():
    """Main bundling process"""
    print("🚀 PLM Log Analyzer - Dependency Bundler")
    print("=" * 50)
    print("This script will download and bundle all dependencies locally.")
    print("Run this ONCE on a machine with internet access.")
    print("Then distribute the entire folder to your team members.")
    print()
    
    # Create directories
    create_directories()
    
    # Download dependencies
    if not download_dependencies():
        print("❌ Failed to download some dependencies. Continuing...")
    
    # Create offline installer
    create_offline_installer()
    
    # Create local requirements
    create_requirements_local()
    
    # Create README
    create_readme()
    
    print()
    print("🎉 Dependency bundling completed!")
    print("📁 Your project now contains:")
    print("   - libs/ folder with all dependencies")
    print("   - install_dependencies.py (offline installer)")
    print("   - requirements_local.txt (local requirements)")
    print("   - README.md (team instructions)")
    print()
    print("📦 To distribute to your team:")
    print("   1. Zip the entire PlmAnalyzer folder")
    print("   2. Share with team members")
    print("   3. They run: python install_dependencies.py")
    print("   4. Then: python app.py")

if __name__ == "__main__":
    main()
