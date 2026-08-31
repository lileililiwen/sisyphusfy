# GitHub Pages Deployment

This document describes how to set up GitHub Pages with a custom domain for Sisyphusfy.

## Prerequisites

- Repository: `lileililiwen/sisyphusfy`
- Custom domain: `about.tooosall.uk`
- DNS provider access for `about.tooosall.uk`

## Steps

### 1. Configure DNS

Add these DNS records at your provider:

| Type | Name | Value |
|------|------|-------|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| CNAME | www | lileililiwen.github.io |

### 2. Enable GitHub Pages

1. Go to repository **Settings** > **Pages**
2. Under **Source**, select **Deploy from a branch**
3. Select branch: `main`
4. Select folder: `/ (root)`
5. Click **Save**

### 3. Configure Custom Domain

1. In **Settings** > **Pages**, enter `about.tooosall.uk` in the **Custom domain** field
2. Click **Save**
3. Wait for DNS check to complete (may take up to 24 hours)
4. Check **Enforce HTTPS** once the certificate is issued

### 4. Verify

1. Visit `https://about.tooosall.uk/`
2. Confirm the site loads over HTTPS
3. Verify the SSL certificate shows GitHub Pages

## Repository URLs

These URLs work regardless of custom domain configuration:

- **Repository**: https://github.com/lileililiwen/sisyphusfy
- **Releases**: https://github.com/lileililiwen/sisyphusfy/releases
- **Raw files**: https://raw.githubusercontent.com/lileililiwen/sisyphusfy/main/

## npm Package Publication

The release workflow publishes `npm/package.json` automatically when a `v*`
tag is pushed. It uses npm trusted publishing, so no long-lived npm token is
stored in GitHub Actions.

Before the first npm release, create the package at npmjs.org or publish it
once manually, then configure its trusted publisher:

1. Sign in to [npmjs.com](https://www.npmjs.com/) with the package-owner account.
2. Open the `sisyphusfy` package settings, or create the package by publishing
   `npm/` once with `npm publish --access public`.
3. Add a GitHub Actions trusted publisher with:
   - Organization/user: `lileililiwen`
   - Repository: `sisyphusfy`
   - Workflow filename: `.github/workflows/release.yml`
   - Environment: leave blank; the npm job does not use a GitHub environment
4. Ensure the package is public and the npm account can publish it.

The existing `v0.1.0` GitHub release predates npm publication. To make that
version installable, publish `npm/` once after configuring the package. Future
version tags will publish automatically through the workflow.

Verify availability with:

```bash
npm view sisyphusfy version
npm install -g sisyphusfy
```

## Troubleshooting

### DNS not resolving

- Wait up to 24 hours for propagation
- Check DNS records with `dig about.tooosall.uk`
- Verify GitHub Pages is enabled in repository settings

### Certificate not issuing

- Ensure DNS points to GitHub Pages IPs
- Check the custom domain field in Pages settings
- Remove and re-add the custom domain

### Site not loading

- Check the Actions tab for deployment errors
- Verify the branch and folder in Pages settings
- Try the `.github.io` URL first: `https://lileililiwen.github.io/sisyphusfy/`
