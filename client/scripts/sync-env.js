#!/usr/bin/env node

/**
 * Sync root .env file environment variables to client/.env.local
 * This script prepends EXPO_PUBLIC_ to variables needed by the client
 * Run this before starting the Expo dev server: npm run sync-env && npm start
 */

const fs = require('fs');
const path = require('path');

// Calculate paths relative to workspace root
const WORKSPACE_ROOT = path.join(__dirname, '../../');
const ROOT_ENV_PATH = path.join(WORKSPACE_ROOT, '.env.local');
const CLIENT_DIR = path.join(WORKSPACE_ROOT, 'client');
const CLIENT_ENV_LOCAL_PATH = path.join(CLIENT_DIR, '.env.local');

// Variables to sync from root .env to client (with EXPO_PUBLIC_ prefix)
const SYNC_VARIABLES = ['DEV_MACHINE_IP', 'USE_SIMULATOR', 'PRODUCTION_API_URL', 'USE_PRODUCTION_API'];

try {
  // Read root .env file
  if (!fs.existsSync(ROOT_ENV_PATH)) {
    console.error(`❌ Root .env file not found at: ${ROOT_ENV_PATH}`);
    process.exit(1);
  }

  const rootEnvContent = fs.readFileSync(ROOT_ENV_PATH, 'utf-8');
  
  // Parse root .env file
  const rootEnv = {};
  rootEnvContent.split('\n').forEach((line) => {
    if (!line || line.startsWith('#')) return;
    const [key, ...valueParts] = line.split('=');
    const trimmedKey = key?.trim();
    if (trimmedKey) {
      const value = valueParts.join('=').trim().replace(/^["']|["']$/g, '');
      rootEnv[trimmedKey] = value;
    }
  });

  // Create client .env.local with EXPO_PUBLIC_ prefix
  let clientEnvContent = `# Auto-generated from root .env file\n`;
  clientEnvContent += `# Auto sync: npm run sync-env\n`;
  clientEnvContent += `# DO NOT commit this file\n\n`;

  SYNC_VARIABLES.forEach((varName) => {
    const value = rootEnv[varName];
    if (value !== undefined) {
      clientEnvContent += `EXPO_PUBLIC_${varName}=${value}\n`;
      console.log(`✓ Synced: EXPO_PUBLIC_${varName}=${value}`);
    } else {
      console.warn(`⚠ Warning: ${varName} not found in root .env`);
    }
  });

  // Write client .env.local
  fs.writeFileSync(CLIENT_ENV_LOCAL_PATH, clientEnvContent);
  console.log(`\n✅ Successfully synced environment variables to: ${CLIENT_ENV_LOCAL_PATH}`);
  console.log('   Start the dev server with: npm start');
} catch (error) {
  console.error('❌ Error syncing environment variables:', error.message);
  process.exit(1);
}
