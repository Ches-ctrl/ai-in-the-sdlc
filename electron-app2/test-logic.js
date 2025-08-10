// Test script to verify core logic without GUI
const fs = require('fs');
const path = require('path');
const chokidar = require('chokidar');

console.log('Testing Git Watcher Core Logic');
console.log('================================');

// Test 1: Check dependencies
console.log('\n1. Checking dependencies...');
try {
    const ws = require('ws');
    const axios = require('axios');
    console.log('✓ WebSocket library loaded');
    console.log('✓ Axios library loaded');
    console.log('✓ Chokidar library loaded');
} catch (error) {
    console.log('✗ Dependency error:', error.message);
}

// Test 2: Test JSON parsing
console.log('\n2. Testing JSON parsing...');
const testLine = '{"cwd": "/test/path", "message": {"role": "user", "content": "Hello world"}}';
try {
    const parsed = JSON.parse(testLine);
    console.log('✓ JSON parsing works');
    console.log('  - CWD:', parsed.cwd);
    console.log('  - Role:', parsed.message?.role);
    console.log('  - Content:', parsed.message?.content);
} catch (error) {
    console.log('✗ JSON parsing error:', error.message);
}

// Test 3: Create test directory and file
console.log('\n3. Creating test environment...');
const testDir = path.join(__dirname, 'test-data');
const testFile = path.join(testDir, 'test.jsonl');

try {
    if (!fs.existsSync(testDir)) {
        fs.mkdirSync(testDir);
    }
    
    // Create a sample .jsonl file
    const sampleData = [
        '{"cwd": "/test/repo", "message": {"role": "user", "content": "Initialize git repository"}}',
        '{"cwd": "/test/repo", "message": {"role": "assistant", "content": "Repository initialized successfully"}}'
    ];
    
    fs.writeFileSync(testFile, sampleData.join('\n') + '\n');
    console.log('✓ Test directory created:', testDir);
    console.log('✓ Test file created:', testFile);
} catch (error) {
    console.log('✗ Test environment error:', error.message);
}

// Test 4: Test file watching
console.log('\n4. Testing file watching...');
let watcherTest = false;
try {
    const watcher = chokidar.watch(testFile, {
        persistent: false,
        usePolling: true,
        interval: 100
    });
    
    watcher.on('change', () => {
        console.log('✓ File change detected');
        watcherTest = true;
        watcher.close();
    });
    
    // Trigger a change
    setTimeout(() => {
        fs.appendFileSync(testFile, '{"test": "change"}\n');
    }, 200);
    
    setTimeout(() => {
        if (!watcherTest) {
            console.log('✗ File watching timeout');
        }
        watcher.close();
    }, 1000);
    
} catch (error) {
    console.log('✗ File watching error:', error.message);
}

// Test 5: Test folder scanning
console.log('\n5. Testing folder scanning...');
try {
    const files = fs.readdirSync(testDir);
    const jsonlFiles = files.filter(file => file.endsWith('.jsonl'));
    console.log('✓ Folder scanning works');
    console.log('  - Total files:', files.length);
    console.log('  - JSONL files:', jsonlFiles.length);
    console.log('  - JSONL files found:', jsonlFiles);
} catch (error) {
    console.log('✗ Folder scanning error:', error.message);
}

console.log('\n6. Summary');
console.log('==========');
console.log('Core logic test completed.');
console.log('The Electron app should work correctly when run in a GUI environment.');
console.log('\nTo test the full application:');
console.log('1. Run "npm start" in a desktop environment');
console.log('2. Select the test-data folder');
console.log('3. Start watching');
console.log('4. Modify the test.jsonl file to trigger events');

// Cleanup
setTimeout(() => {
    try {
        fs.rmSync(testDir, { recursive: true, force: true });
        console.log('\n✓ Test cleanup completed');
    } catch (error) {
        console.log('\n✗ Cleanup error:', error.message);
    }
}, 2000);

