const assert = require('node:assert/strict');
const test = require('node:test');

const { getMainBinaryName, prepareTauriConfig, configureCompression } = require('./build-config');

test('uses the app name as the Tauri main binary', () => {
    assert.equal(getMainBinaryName('ok-script-app'), 'ok-script-app');
});

test('changes NSIS compression while preserving installer settings', () => {
    const source = JSON.stringify({bundle: {windows: {nsis: {template: 'installer.nsi', languages: ['English']}}}});
    const config = JSON.parse(configureCompression(source, 'zlib'));
    assert.equal(config.bundle.windows.nsis.compression, 'zlib');
    assert.equal(config.bundle.windows.nsis.template, 'installer.nsi');
    assert.deepEqual(config.bundle.windows.nsis.languages, ['English']);
});

test('rejects unsupported NSIS compression', () => {
    assert.throws(() => configureCompression('{}', 'unexpected'), /Unsupported NSIS compression/);
});

test('prepares tauri.conf.json without relying on exact serialized strings', () => {
    const source = JSON.stringify({
        productName: 'pyappify',
        mainBinaryName: 'pyappify Launcher',
        version: '0.0.1',
        identifier: 'pyappify',
        app: { windows: [{ title: 'pyappify' }] },
    });

    const result = JSON.parse(prepareTauriConfig(source, 'ok-script-app', 'v1.1.15'));

    assert.equal(result.productName, 'ok-script-app');
    assert.equal(result.mainBinaryName, 'ok-script-app');
    assert.equal(result.version, '1.1.15');
    assert.equal(result.identifier, 'ok-script-app');
    assert.equal(result.app.windows[0].title, 'ok-script-app');
});
