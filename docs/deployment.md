# GitHub Pages Deployment

This document describes how to set up GitHub Pages with a custom domain for Sisyphusfy.

## Prerequisites

- Repository: `lileililiwen/sisyphusfy`
- Custom domain: `sisyphusfy.dev`
- DNS provider access for `sisyphusfy.dev`

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

1. In **Settings** > **Pages**, enter `sisyphusfy.dev` in the **Custom domain** field
2. Click **Save**
3. Wait for DNS check to complete (may take up to 24 hours)
4. Check **Enforce HTTPS** once the certificate is issued

### 4. Verify

1. Visit `https://sisyphusfy.dev/`
2. Confirm the site loads over HTTPS
3. Verify the SSL certificate shows GitHub Pages

## Repository URLs

These URLs work regardless of custom domain configuration:

- **Repository**: https://github.com/lileililiwen/sisyphusfy
- **Releases**: https://github.com/lileililiwen/sisyphusfy/releases
- **Raw files**: https://raw.githubusercontent.com/lileililiwen/sisyphusfy/main/

## Troubleshooting

### DNS not resolving

- Wait up to 24 hours for propagation
- Check DNS records with `dig sisyphusfy.dev`
- Verify GitHub Pages is enabled in repository settings

### Certificate not issuing

- Ensure DNS points to GitHub Pages IPs
- Check the custom domain field in Pages settings
- Remove and re-add the custom domain

### Site not loading

- Check the Actions tab for deployment errors
- Verify the branch and folder in Pages settings
- Try the `.github.io` URL first: `https://lileililiwen.github.io/sisyphusfy/`
