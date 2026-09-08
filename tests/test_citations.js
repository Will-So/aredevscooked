// Run with node --test tests/test_citations.js.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('website/script.js', 'utf8');
const context = {document: {readyState: 'loading', addEventListener() {}}, Intl, URL};
vm.createContext(context);
vm.runInContext(source.replace('    // Initialize on DOM ready', '    globalThis.renderCitations = renderCitations;\n    // Initialize on DOM ready'), context);

test('period numbers stay fixed despite source order, duplicates, and missing sources', () => {
    const html = context.renderCitations({
        source_url: 'https://example.com/current',
        source_urls: ['https://example.com/unrelated'],
        changes: {
            q1_2023: {source_url: 'https://example.com/2023'},
            '1_year_ago': {source_url: 'https://example.com/year'},
            '30_days_ago': {source_url: 'https://example.com/current'},
        },
    });
    assert.match(html, /href="https:\/\/example.com\/current"[^>]*>\[1\]/);
    assert.match(html, /href="https:\/\/example.com\/current"[^>]*>\[2\]/);
    assert.match(html, /href="https:\/\/example.com\/year"[^>]*>\[3\]/);
    assert.match(html, /title="Q1 2023 source"[^>]*>\[4\]/);
    assert.ok(!html.includes('unrelated'));
    const missing = context.renderCitations({changes: {'1_year_ago': {source_url: 'https://example.com/year'}}});
    assert.match(missing, /30 days ago: source unavailable/);
    assert.match(missing, /\[3\]<\/a>/);
});

test('only supporting sources use extra numbers; unsafe links are omitted', () => {
    const html = context.renderCitations({source_url: 'javascript:alert(1)', additional_source_urls: ['https://example.com/adjustment']});
    assert.ok(!html.includes('javascript:'));
    assert.match(html, /title="Current supporting source source"[^>]*>\[4\]/);
});
