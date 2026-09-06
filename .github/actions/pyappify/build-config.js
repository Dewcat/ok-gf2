function replaceExactStringValues(value, from, to) {
    if (typeof value === 'string') {
        return value === from ? to : value;
    }

    if (Array.isArray(value)) {
        return value.map(item => replaceExactStringValues(item, from, to));
    }

    if (value && typeof value === 'object') {
        return Object.fromEntries(
            Object.entries(value).map(([key, item]) => [
                key,
                replaceExactStringValues(item, from, to),
            ]),
        );
    }

    return value;
}

function getMainBinaryName(appName) {
    return appName;
}

function prepareTauriConfig(contents, appName, version) {
    let config = JSON.parse(contents);
    config = replaceExactStringValues(config, 'pyappify', appName);
    config = replaceExactStringValues(config, '0.0.1', version.replace(/^v/, ''));
    config.mainBinaryName = getMainBinaryName(appName);

    return `${JSON.stringify(config, null, 2)}\n`;
}

function configureCompression(contents, compression) {
    if (!['zlib', 'lzma', 'bzip2', 'none'].includes(compression)) {
        throw new Error(`Unsupported NSIS compression: ${compression}`);
    }
    const config = JSON.parse(contents);
    config.bundle.windows.nsis.compression = compression;
    return JSON.stringify(config, null, 2);
}

module.exports = {
    configureCompression,
    getMainBinaryName,
    prepareTauriConfig,
};
