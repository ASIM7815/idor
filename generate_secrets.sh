#!/bin/bash
# Generate Secrets for Render Deployment
# Run this script to generate secure values for environment variables

echo "==================================="
echo "Leaky Invoice - Secret Generator"
echo "==================================="
echo ""

echo "Copy these values to your Render dashboard:"
echo ""

echo "1. LEAKY_INVOICE_SECRET_KEY:"
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "   $SECRET_KEY"
echo ""

echo "2. LEAKY_INVOICE_FLAG (example - customize this!):"
echo "   FLAG{r3nd3r_1d0r_ch4ll3ng3_$(date +%Y)}"
echo ""

echo "3. Other required variables:"
echo "   LEAKY_INVOICE_DATABASE=/data/leaky_invoices.db"
echo "   FLASK_ENV=production"
echo ""

echo "==================================="
echo "Steps to deploy to Render:"
echo "==================================="
echo ""
echo "1. Go to https://dashboard.render.com"
echo "2. New + → Web Service"
echo "3. Connect your GitHub repo: ASIM7815/idor"
echo "4. Environment: Docker"
echo "5. Add environment variables above (click Advanced)"
echo "6. Set health check path: /health"
echo "7. Click 'Create Web Service'"
echo ""
echo "Important: Set LEAKY_INVOICE_FLAG and LEAKY_INVOICE_SECRET_KEY"
echo "           as 'Secret' type in Render for security!"
echo ""
