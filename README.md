# Web Clipper Skill

Save web articles as Markdown files with images to local storage.

## Features

- **Site-specific parsers** for: 华尔街见闻, 少数派, Bilibili, 微信公众号
- **Generic HTML parser** for other sites
- **Image download** with local storage
- **Self-healing**: Health tracking, failure diagnosis, evolution reports
- **Pure Python 3 standard library** - no pip dependencies

## Usage

```bash
python3 scripts/clipper.py "<URL>"
```

## Supported Sites

| Site | Domain |
|------|--------|
| 华尔街见闻 | wallstreetcn.com |
| 少数派 | sspai.com |
| Bilibili | bilibili.com |
| 微信公众号 | mp.weixin.qq.com |

## Parser Evolution

When parsers break due to website structure changes:
1. Check `evolution-reports/` for failure details
2. Analyze HTML sample
3. Update parser in `scripts/clipper.py`
4. Test with `--test` flag

## License

MIT
