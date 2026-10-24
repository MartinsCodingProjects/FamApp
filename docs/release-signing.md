# Release signing

How the signed release APK is built, and what Martin sets up for it (M3, C3.8). Workflow: `.github/workflows/release.yml`.

- Runs **only on push to `release`** (only Martin moves it). No PR trigger, so pull requests and forks never get the secrets. No other workflow reads them.
- Reads `app/version.json` (`versionName`, `versionCode`) and **fails if `versionCode` is not higher** than the last GitHub Release's (tag `app-v<versionName>-<versionCode>`, e.g. `app-v0.1.0-1`).
- Builds the release APK, signs it with the key from the secrets (`apksigner`), and attaches it to a new GitHub Release.
- PR and `main` builds stay debug-signed and only exist as CI artifacts.

Updates install only if they are signed with **the same key**. Losing the key means uninstalling the app on both phones (and losing local state) to install a newly signed one.

## Secret names

| Secret | Content |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | the keystore file, base64 encoded (one line) |
| `ANDROID_KEYSTORE_PASSWORD` | keystore password |
| `ANDROID_KEY_ALIAS` | key alias inside the keystore (`famapp` below) |
| `ANDROID_KEY_PASSWORD` | key password (with a PKCS12 keystore the same as the keystore password) |

## M3: create the key (Martin, once, on the notebook)

Needs a JDK (`keytool`). Never on the home server, never in the repo.

```sh
keytool -genkeypair -v \
  -keystore famapp-release.keystore -storetype PKCS12 \
  -alias famapp -keyalg RSA -keysize 4096 -validity 36500 \
  -dname "CN=famapp"
```

- Choose a long random password; with PKCS12 the key password is the same as the keystore password.
- `-validity 36500` (100 years): Android never accepts a new key for an installed app, so the key must outlive the app.
- `CN=famapp` keeps names out of the certificate (the certificate is readable from every APK).

**Back it up twice** before doing anything else: the keystore file plus the password, in two separate places (e.g. password manager with file attachment, and an encrypted USB stick kept elsewhere). Check that both copies open: `keytool -list -keystore <copy> -storetype PKCS12`.

## M3: add the secrets (until C3: Environment `release`)

1. Repo → Settings → Environments → **New environment** `release`.
   - Deployment branches and tags: **Selected branches** → `release` only.
   - **Required reviewers:** Martin. Every release run then waits for his approval.
2. Add the four secrets **to the environment** (not as repo secrets):
   ```sh
   base64 -w0 famapp-release.keystore   # macOS: base64 -i famapp-release.keystore
   ```
   paste the output as `ANDROID_KEYSTORE_BASE64`; the passwords and alias (`famapp`) as the other three.
3. Protect `release`: only Martin may push (ruleset on `release`: restrict updates to Martin; block force pushes and deletion).
4. Delete any extra local copies of the base64 text.

The first run happens when Martin first moves `release` (C1). Then check: the run waited for approval, a GitHub Release `app-v…` exists with the APK, and the log shows the certificate's SHA-256 (note it; every later APK must show the same).

## C3.8: switch to repo secrets (repo goes private on GitHub Free)

Private repos on GitHub Free have no Environment secrets and no required reviewers (`docs/decisions.md` section 10).

1. Before making the repo private: Settings → Secrets and variables → Actions → **Repository secrets**: add the same four secrets under the same names.
2. The one switch in the workflow: an agent PR deletes the line `environment: release` from `.github/workflows/release.yml` (marked with a comment). Nothing else changes; the secret names stay.
3. Make the repo private, then delete the Environment `release` (its secrets are no longer readable anyway).
4. From now on the release workflow is the only one that reads the secrets; no approval step any more, so only pushing `release` (Martin) releases.

## Version bumps

The agent bumps `versionCode` (+1) and, if needed, `versionName` in `app/version.json` in the PR that asks Martin to move `release` (end of Runs 2, 3, 4 or a bug-fix release). If the release run fails with "versionCode must be higher", that bump is missing.
