# Web Clipper Skill - Changelog

## [2.0.0] - 2026-05-02

### Added
- Site-specific parser registry with `@register_parser` decorator
- Parsers for: wallstreetcn.com, sspai.com, bilibili.com, mp.weixin.qq.com
- Parser health tracking (success/failure rates)
- Automatic failure diagnosis with suggestions
- Evolution reports saved to `evolution-reports/`
- Fallback chain: site-specific → generic → Playwright suggestion
- Image deduplication and small icon filtering
- HTTP → HTTPS conversion for image URLs
- WeChat article noise cleanup (UI text removal)

### Changed
- Major refactor from single parser to modular architecture
- `fetch_url()` now returns `(html, final_url)` for redirect handling
- `clip_article()` uses final URL for domain matching

### Technical Details
- Pure Python 3 standard library (no pip dependencies)
- Mobile User-Agent (iPhone Safari) for better content access
- JSON embedded data extraction for JS-rendered sites
- HTML structure parsing for server-rendered sites

## [1.5.0] - 2026-05-02

### Fixed
- Content extraction with manual quote scanning (handles unescaped quotes)
- Article ID matching for multi-article pages (Wall Street CN)

## [1.4.0] - 2026-05-02

### Fixed
- Title matching for pages with multiple articles

## [1.3.0] - 2026-05-02

### Enhanced
- Inline content extraction with proper escape handling

## [1.2.0] - 2026-05-02

### Enhanced
- JSON data extraction for `__NEXT_DATA__`, `__INITIAL_STATE__`

## [1.1.0] - 2026-05-02

### Fixed
- User-Agent changed to mobile iPhone Safari
- Critical for JS-rendered sites (Wall Street CN)

## [1.0.0] - 2026-05-02

### Initial Release
- Basic HTML parser with generic extraction
- Title, content, and image extraction
- Markdown conversion
- Local file saving
