# Deployment, storage, and recovery

## Local use

Run one application process for the private data directory. The default binds to `127.0.0.1:4318`, and local access is treated as the owner. On a shared machine, issue an owner token and require authentication:

```sh
python3 -m keystone token --data ./data --role owner --author "Library owner"
python3 -m keystone serve --data ./data --require-auth
```

The library is plain local data. Use operating-system account permissions and disk protection appropriate to its contents. The default is not encrypted vault storage.

## Shared reader service

Keep private runtime data on a controlled host. Use HTTPS for remote access, preserve the original Host header, and allow only your intended hostnames. Behind a reverse proxy, start the app with `--require-auth` even if its bind address is loopback; otherwise proxy requests would be treated as local-owner requests.

```sh
python3 -m keystone serve --data /srv/keystone-private \
  --host 127.0.0.1 --port 4318 --require-auth \
  --public-host knowledge.example.com
```

The hostname above is illustrative. Configure the real DNS, certificates, firewall, reverse proxy, and service supervision for your environment. The toolkit does not provision those services. Keep the raw application port private. Do not expose a local MCP subprocess as a network service.

Issue individual reader or author credentials from the host. Reader credentials only expose verified content. Author credentials can write drafts but cannot verify them. Owner credentials manage the library and storage settings. There is no per-document permission model: anyone with a role can access the content that role permits across the library.

Do not place credentials in URLs, public issues, documentation, or repository settings. The configuration stores token hashes. This release does not provide a full identity lifecycle or enterprise SSO. To revoke a credential when no dedicated management interface is available, stop the service, remove its corresponding token entry from the private configuration, and restart; preserve unrelated entries and issue a replacement when needed.

## Backup choices

**Local:** choose a folder outside the vault. A separate disk or host protects against more failure modes than the same disk. Snapshots have unique names and a checksum manifest.

**Cloud:** install rclone, configure a remote for your chosen provider, and select its `remote:path` in Keystone settings. Keystone creates a local snapshot, then uploads it using the configured remote. If upload fails, the local snapshot remains and the result reports cloud failure. Configure an rclone crypt remote when client-side encryption is desired. Protect its password and recovery information separately. [rclone crypt documentation](https://rclone.org/crypt/)

The default local snapshots are unencrypted. Cloud encryption depends on the selected remote; a cloud destination alone is not an encryption guarantee. Backups are run on demand in this version. There is no automatic schedule or retention policy unless you configure one externally.

Snapshots contain files under the dedicated vault, including its Obsidian settings if present. They exclude the enclosing installation configuration and access credentials. Avoid storing unrelated sensitive files in the vault and use only trusted Obsidian plugins. Symlinks are rejected by the snapshot workflow.

## Recovery test

Restore is intentionally non-destructive. It checks the archive manifest and file hashes, rejects unsafe paths, and refuses a nonempty target folder. The current restore limit is 2 GiB of uncompressed content.

1. Keep the original installation and archive intact.
2. Initialize a fresh data directory:

   ```sh
   python3 -m keystone init --data ./recovered-data --author "Your name"
   ```

3. In the file manager, rename the new `recovered-data/vault` folder to `starter-vault`, preserving its generated examples.
4. Restore the snapshot into the now-absent vault folder:

   ```sh
   python3 scripts/restore.py /path/to/keystone-snapshot.zip --to ./recovered-data/vault
   python3 -m keystone serve --data ./recovered-data
   ```

5. Search recent documents, read their content, and inspect expected workflow files. Record the archive, recovery date, checks, and limitations.
6. Configure the intended backup destination and issue new credentials before sharing this recovered installation. Open the recovered `vault` directory separately in Obsidian.

Checksum verification detects accidental corruption and changes relative to the archive's manifest. It does not authenticate who created an archive or replace a practical recovery test. Use archives from trusted sources.

## Static export

`scripts/export_reader.py` creates a read-only website from verified documents. Its output has no server-side authentication and is not encrypted. The hosting layer controls access to every included file. Treat the output as a copy of the included documentation and select the audience before publishing it.

The public toolkit repository and a private engineering library are separate things. GitHub can host the code without hosting private content. This repository's Actions workflow runs tests; it does not publish the private library or deploy GitHub Pages.
