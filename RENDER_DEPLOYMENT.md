# Deploying to Render

This guide covers deploying The Leaky Invoice CTF challenge to Render.

## Quick Setup

### 1. Prerequisites
- GitHub repository (already done ✅)
- Render account (sign up at https://render.com)

### 2. Deploy to Render

#### Option A: Using Render Dashboard (Recommended)

1. **Go to Render Dashboard**: https://dashboard.render.com

2. **Create New Web Service**:
   - Click "New +" → "Web Service"
   - Connect your GitHub account if not already connected
   - Select repository: `ASIM7815/idor`
   - Click "Connect"

3. **Configure Service**:
   - **Name**: `leaky-invoice` (or your preferred name)
   - **Region**: Choose closest to your users
   - **Branch**: `main`
   - **Root Directory**: Leave empty (or `.` if needed)
   - **Environment**: `Docker`
   - **Plan**: Free (or paid for better performance)

4. **Set Environment Variables** (CRITICAL):
   Click "Advanced" and add these environment variables:

   | Key | Value | Type |
   |-----|-------|------|
   | `LEAKY_INVOICE_FLAG` | `FLAG{your_unique_ctf_flag_here}` | Secret |
   | `LEAKY_INVOICE_SECRET_KEY` | Generate with command below | Secret |
   | `LEAKY_INVOICE_DATABASE` | `/data/leaky_invoices.db` | Plain |
   | `FLASK_ENV` | `production` | Plain |

   **Generate Secret Key**:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

5. **Configure Health Check** (Optional but recommended):
   - Health Check Path: `/health`

6. **Deploy**:
   - Click "Create Web Service"
   - Wait for deployment to complete (3-5 minutes)

#### Option B: Using render.yaml (Infrastructure as Code)

1. The repository includes `render.yaml` for automatic configuration

2. **Important**: You still need to set secrets in Render dashboard:
   - Go to your service → Environment
   - Add `LEAKY_INVOICE_FLAG` and `LEAKY_INVOICE_SECRET_KEY`

3. Render will automatically use the `render.yaml` configuration

### 3. Verify Deployment

Once deployed, test your application:

```bash
# Replace with your Render URL
RENDER_URL="https://your-app-name.onrender.com"

# Test health check
curl $RENDER_URL/health

# Test home page
curl -I $RENDER_URL/

# Test robots.txt
curl $RENDER_URL/robots.txt
```

### 4. Access Your Application

Your CTF challenge will be available at:
```
https://your-app-name.onrender.com
```

Demo credentials:
- Username: `alice`
- Password: `password123`

## Environment Variables Reference

### Required (Must be set as SECRETS in Render):

**LEAKY_INVOICE_FLAG**
- Your unique CTF flag
- Example: `FLAG{r3nd3r_1d0r_ch4ll3ng3}`
- **MUST BE UNIQUE** per event
- Keep this secret until after the event

**LEAKY_INVOICE_SECRET_KEY**
- Flask session encryption key
- Generate with: `python3 -c "import secrets; print(secrets.token_hex(32))"`
- Example: `a1b2c3d4e5f6...` (64 characters)
- Must be random and secure

### Optional (Can be plain text):

**LEAKY_INVOICE_DATABASE**
- Default: `/data/leaky_invoices.db`
- Don't change unless you have specific requirements

**FLASK_ENV**
- Default: `production`
- Options: `production` or `development`
- Use `production` for Render

## Troubleshooting

### Error: "LEAKY_INVOICE_FLAG environment variable is required"

**Solution**: You forgot to set the environment variables in Render dashboard.

1. Go to your service in Render dashboard
2. Click "Environment" in the left sidebar
3. Add the required environment variables (see above)
4. Click "Save Changes"
5. Render will automatically redeploy

### Error: "LEAKY_INVOICE_SECRET_KEY environment variable is required"

**Solution**: Same as above - add the secret key to environment variables.

### Database persistence issues

On Render's free tier, the filesystem is ephemeral. For persistence:

1. **Upgrade to paid plan** for persistent disk, OR
2. **Accept ephemeral data** - database resets on each deploy (OK for CTF events)

For persistent storage:
1. Go to service settings
2. Add a "Disk" under "Environment"
3. Mount path: `/data`
4. Size: 1 GB (minimum)

### Deployment keeps failing

1. **Check logs**:
   - Go to your service → "Logs"
   - Look for specific error messages

2. **Verify Dockerfile builds locally**:
   ```bash
   docker build -t leaky-invoice .
   docker run -e LEAKY_INVOICE_FLAG='test' \
              -e LEAKY_INVOICE_SECRET_KEY='test' \
              leaky-invoice
   ```

3. **Check environment variables**:
   - Ensure no typos in variable names
   - Ensure values are not empty
   - Ensure secrets are marked as "Secret" type

### Application is slow (Free tier)

Render's free tier:
- Spins down after 15 minutes of inactivity
- First request after spin-down takes 30-60 seconds
- Subsequent requests are fast

**Solutions**:
1. Upgrade to paid plan (starts at $7/month)
2. Use a uptime monitor to ping your app every 10 minutes
3. Warn participants about initial load time

### Health check failing

1. Verify health endpoint works:
   ```bash
   curl https://your-app.onrender.com/health
   ```

2. If it fails, check:
   - Database initialization completed
   - No errors in application logs
   - Port 5000 is exposed (already in Dockerfile)

## Render-Specific Configuration

### Build Settings
- **Build Command**: Handled by Dockerfile
- **Start Command**: Handled by Dockerfile CMD (./start.sh)
- **Environment**: Docker

### Service Settings
- **Auto-Deploy**: Enable (recommended)
- **Branch**: main
- **Health Check Path**: /health
- **Health Check Interval**: 30 seconds

### Scaling (Paid Plans)
For high traffic events:
- **Instance Type**: Upgrade from Free to Starter ($7) or Standard ($25)
- **Instances**: Scale horizontally for more traffic
- **Persistent Disk**: Add for database persistence

## Security Checklist for Render

- [x] `LEAKY_INVOICE_FLAG` set as Secret (not plain text)
- [x] `LEAKY_INVOICE_SECRET_KEY` set as Secret (not plain text)
- [x] HTTPS enabled (automatic on Render)
- [x] Environment variables not in code/Dockerfile
- [x] `.gitignore` prevents committing secrets
- [x] Health checks configured
- [x] Production mode enabled (`FLASK_ENV=production`)

## Cost Estimates

### Free Tier
- **Cost**: $0/month
- **Limitations**:
  - 750 hours/month
  - Spins down after 15 min inactivity
  - Ephemeral filesystem
  - Lower resources
- **Good for**: Testing, small events, demos

### Starter Plan
- **Cost**: $7/month
- **Benefits**:
  - Always running
  - Persistent disk available
  - More resources
- **Good for**: Small to medium CTF events

### Standard Plan
- **Cost**: $25/month
- **Benefits**:
  - More CPU/RAM
  - Better performance
  - Persistent disk included
- **Good for**: Large CTF events with many participants

## Monitoring Your Deployment

### Built-in Monitoring (Render Dashboard)
- **Logs**: Real-time application logs
- **Metrics**: CPU, Memory, Response times
- **Events**: Deploy history, crashes, restarts

### External Monitoring (Optional)
Set up uptime monitoring:
- UptimeRobot (free tier available)
- Pingdom
- StatusCake

Monitor URL: `https://your-app.onrender.com/health`

## Updating Your Application

### Automatic Deployment
1. Push changes to GitHub
2. Render automatically deploys
3. Zero downtime deployment

### Manual Deployment
1. Go to Render dashboard
2. Click "Manual Deploy" → "Deploy latest commit"

### Rollback
1. Go to "Events" in Render dashboard
2. Find successful previous deploy
3. Click "Rollback"

## CTF Event Preparation

### Before the Event
1. Deploy to Render
2. Test all functionality
3. Verify IDOR vulnerability works
4. Test with demo credentials
5. Set up monitoring
6. Document the URL for participants
7. Consider upgrading to paid plan for stability

### During the Event
1. Monitor logs for issues
2. Watch metrics for performance
3. Be ready to scale if needed

### After the Event
1. Optionally share solutions
2. Consider keeping deployed for educational use
3. Rotate flag for next event
4. Archive/export database if needed

## Quick Reference

### Environment Variables to Set in Render:
```bash
LEAKY_INVOICE_FLAG=FLAG{your_unique_flag}
LEAKY_INVOICE_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
LEAKY_INVOICE_DATABASE=/data/leaky_invoices.db
FLASK_ENV=production
```

### Health Check URL:
```
https://your-app-name.onrender.com/health
```

### Demo Credentials:
```
Username: alice
Password: password123
```

### Support
- Render Docs: https://render.com/docs
- Render Status: https://status.render.com
- Application Logs: Render Dashboard → Your Service → Logs

---

**Ready to deploy!** Follow the steps above and your CTF challenge will be live in minutes. 🚀
