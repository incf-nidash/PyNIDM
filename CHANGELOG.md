# v4.1.0 (Sat Jul 22 2023)

#### 🚀 Enhancement

- updated nidm model to collections of entities [#378](https://github.com/incf-nidash/PyNIDM/pull/378) ([@dbkeator](https://github.com/dbkeator))

#### Authors: 1

- David Keator ([@dbkeator](https://github.com/dbkeator))

---

# v4.0.0 (Tue May 30 2023)

#### 💥 Breaking Change

- [gh-actions](deps): Bump codespell-project/actions-codespell from 1 to 2 [#375](https://github.com/incf-nidash/PyNIDM/pull/375) ([@dependabot[bot]](https://github.com/dependabot[bot]))

#### 🐛 Bug Fix

- Do not try to upload nonexisting junit artifacts [#372](https://github.com/incf-nidash/PyNIDM/pull/372) ([@yarikoptic](https://github.com/yarikoptic))
- Use RST links in readme [#303](https://github.com/incf-nidash/PyNIDM/pull/303) ([@surchs](https://github.com/surchs) [@yarikoptic](https://github.com/yarikoptic))
- Add 3.10 and 3.11 into testing [#324](https://github.com/incf-nidash/PyNIDM/pull/324) ([@yarikoptic](https://github.com/yarikoptic))
- codespell: action, config + fixes [#321](https://github.com/incf-nidash/PyNIDM/pull/321) ([@yarikoptic](https://github.com/yarikoptic))

#### ⚠️ Pushed to `master`

- Travis is no longer used ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Refactor printing the same text to both stdout and a file [#376](https://github.com/incf-nidash/PyNIDM/pull/376) ([@jwodder](https://github.com/jwodder))
- Set up auto [#346](https://github.com/incf-nidash/PyNIDM/pull/346) ([@jwodder](https://github.com/jwodder))
- Use versioningit [#374](https://github.com/incf-nidash/PyNIDM/pull/374) ([@jwodder](https://github.com/jwodder))
- Assorted minor code improvements [#369](https://github.com/incf-nidash/PyNIDM/pull/369) ([@jwodder](https://github.com/jwodder))
- Open all text files with UTF-8 encoding [#373](https://github.com/incf-nidash/PyNIDM/pull/373) ([@jwodder](https://github.com/jwodder))
- Pare down giant comment blocks that largely do what Git already does [#363](https://github.com/incf-nidash/PyNIDM/pull/363) ([@jwodder](https://github.com/jwodder))
- Improve string formatting syntax [#364](https://github.com/incf-nidash/PyNIDM/pull/364) ([@jwodder](https://github.com/jwodder))
- Don't list `object` as a base class [#365](https://github.com/incf-nidash/PyNIDM/pull/365) ([@jwodder](https://github.com/jwodder))
- Use Python 3-style `super()` calls [#366](https://github.com/incf-nidash/PyNIDM/pull/366) ([@jwodder](https://github.com/jwodder))
- Remove redundant imports [#367](https://github.com/incf-nidash/PyNIDM/pull/367) ([@jwodder](https://github.com/jwodder))
- Clean up Docker-related files [#351](https://github.com/incf-nidash/PyNIDM/pull/351) ([@jwodder](https://github.com/jwodder))
- Enable building docs locally via `tox -e docs` [#357](https://github.com/incf-nidash/PyNIDM/pull/357) ([@jwodder](https://github.com/jwodder))
- Replace uses of `urllib.request` with `requests` [#359](https://github.com/incf-nidash/PyNIDM/pull/359) ([@jwodder](https://github.com/jwodder))
- Delete `profiler.py` [#362](https://github.com/incf-nidash/PyNIDM/pull/362) ([@jwodder](https://github.com/jwodder))
- Add `.coverage` to `.gitignore` [#354](https://github.com/incf-nidash/PyNIDM/pull/354) ([@jwodder](https://github.com/jwodder))
- Shorten overly-long lines of punctuation [#345](https://github.com/incf-nidash/PyNIDM/pull/345) ([@jwodder](https://github.com/jwodder))
- Fix `__version__` import [#353](https://github.com/incf-nidash/PyNIDM/pull/353) ([@jwodder](https://github.com/jwodder))
- Update workflow actions versions and keep them up to date with Dependabot [#350](https://github.com/incf-nidash/PyNIDM/pull/350) ([@jwodder](https://github.com/jwodder))
- Remove fallback to Python 2 import [#348](https://github.com/incf-nidash/PyNIDM/pull/348) ([@jwodder](https://github.com/jwodder))
- Add testing via tox [#334](https://github.com/incf-nidash/PyNIDM/pull/334) ([@jwodder](https://github.com/jwodder))
- Remove Python 2-specific `__future__` imports [#335](https://github.com/incf-nidash/PyNIDM/pull/335) ([@jwodder](https://github.com/jwodder))
- Remove uses of `six` [#336](https://github.com/incf-nidash/PyNIDM/pull/336) ([@jwodder](https://github.com/jwodder))
- Prune `README.md` files from code directories [#338](https://github.com/incf-nidash/PyNIDM/pull/338) ([@jwodder](https://github.com/jwodder))
- Use a `src/` layout [#332](https://github.com/incf-nidash/PyNIDM/pull/332) ([@jwodder](https://github.com/jwodder))
- Run linting as part of CI [#333](https://github.com/incf-nidash/PyNIDM/pull/333) ([@jwodder](https://github.com/jwodder))
- Run tests in CI on pushes & merges to master [#331](https://github.com/incf-nidash/PyNIDM/pull/331) ([@jwodder](https://github.com/jwodder))
- Use `build` in `pythonpublish.yml` [#330](https://github.com/incf-nidash/PyNIDM/pull/330) ([@jwodder](https://github.com/jwodder))
- Add & apply pre-commit and linting [#329](https://github.com/incf-nidash/PyNIDM/pull/329) ([@jwodder](https://github.com/jwodder))
- `docs/build/` should not be committed [#327](https://github.com/incf-nidash/PyNIDM/pull/327) ([@jwodder](https://github.com/jwodder))
- Update Python packaging [#326](https://github.com/incf-nidash/PyNIDM/pull/326) ([@jwodder](https://github.com/jwodder))
- "Splitted" is not a word [#328](https://github.com/incf-nidash/PyNIDM/pull/328) ([@jwodder](https://github.com/jwodder))

#### 📝 Documentation

- Use `.readthedocs.yaml` file to install pynidm in RTD environment [#370](https://github.com/incf-nidash/PyNIDM/pull/370) ([@jwodder](https://github.com/jwodder))
- Clean up `README.rst` markup [#340](https://github.com/incf-nidash/PyNIDM/pull/340) ([@jwodder](https://github.com/jwodder))

#### 🧪 Tests

- Clean up Click testing [#352](https://github.com/incf-nidash/PyNIDM/pull/352) ([@jwodder](https://github.com/jwodder))
- Write test temp files to temp directories [#343](https://github.com/incf-nidash/PyNIDM/pull/343) ([@jwodder](https://github.com/jwodder))
- Measure test coverage [#344](https://github.com/incf-nidash/PyNIDM/pull/344) ([@jwodder](https://github.com/jwodder))
- Make pytest error on warnings [#341](https://github.com/incf-nidash/PyNIDM/pull/341) ([@jwodder](https://github.com/jwodder))
- Replace `tmpdir` fixture with `tmp_path` [#339](https://github.com/incf-nidash/PyNIDM/pull/339) ([@jwodder](https://github.com/jwodder))

#### 🔩 Dependency Updates

- Remove practically-unused `joblib` [#360](https://github.com/incf-nidash/PyNIDM/pull/360) ([@jwodder](https://github.com/jwodder))
- Clean up install requirements [#347](https://github.com/incf-nidash/PyNIDM/pull/347) ([@jwodder](https://github.com/jwodder))
- Replace simplejson with stdlib json [#337](https://github.com/incf-nidash/PyNIDM/pull/337) ([@jwodder](https://github.com/jwodder))

#### Authors: 4

- [@dependabot[bot]](https://github.com/dependabot[bot])
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Sebastian Urchs ([@surchs](https://github.com/surchs))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))
