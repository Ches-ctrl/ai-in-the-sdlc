// Simple packaging script for distribution
const fs = require('fs');
const path = require('path');

console.log('Git Watcher App - Packaging Script');
console.log('==================================');

const appFiles = [
    'main.js',
    'preload.js',
    'index.html',
    'renderer.js',
    'package.json',
    'README.md'
];

const distDir = path.join(__dirname, 'dist-package');

try {
    // Create distribution directory
    if (fs.existsSync(distDir)) {
        fs.rmSync(distDir, { recursive: true, force: true });
    }
    fs.mkdirSync(distDir);
    
    console.log('✓ Created distribution directory');
    
    // Copy application files
    appFiles.forEach(file => {
        const srcPath = path.join(__dirname, file);
        const destPath = path.join(distDir, file);
        
        if (fs.existsSync(srcPath)) {
            fs.copyFileSync(srcPath, destPath);
            console.log(`✓ Copied ${file}`);
        } else {
            console.log(`✗ Missing ${file}`);
        }
    });
    
    // Copy node_modules (essential packages only)
    const nodeModulesDir = path.join(distDir, 'node_modules');
    fs.mkdirSync(nodeModulesDir);
    
    const essentialPackages = ['ws', 'chokidar', 'axios'];
    essentialPackages.forEach(pkg => {
        const srcPath = path.join(__dirname, 'node_modules', pkg);
        const destPath = path.join(nodeModulesDir, pkg);
        
        if (fs.existsSync(srcPath)) {
            fs.cpSync(srcPath, destPath, { recursive: true });
            console.log(`✓ Copied package: ${pkg}`);
        }
    });
    
    // Create installation instructions
    const installInstructions = `# Git Watcher App - Installation

## Quick Start

1. Ensure Node.js and Electron are installed:
   \`\`\`bash
   npm install -g electron
   \`\`\`

2. Run the application:
   \`\`\`bash
   electron .
   \`\`\`

## Full Installation

1. Install all dependencies:
   \`\`\`bash
   npm install
   \`\`\`

2. Run the application:
   \`\`\`bash
   npm start
   \`\`\`

## Building Executable

To create a standalone executable:
\`\`\`bash
npm install electron-builder -g
electron-builder
\`\`\`

The executable will be created in the \`dist\` folder.
`;
    
    fs.writeFileSync(path.join(distDir, 'INSTALL.md'), installInstructions);
    console.log('✓ Created installation instructions');
    
    console.log('\n✓ Packaging completed successfully!');
    console.log(`Distribution package created in: ${distDir}`);
    console.log('\nTo distribute:');
    console.log('1. Zip the dist-package folder');
    console.log('2. Share with users');
    console.log('3. Users can follow INSTALL.md instructions');
    
} catch (error) {
    console.log('✗ Packaging error:', error.message);
}

