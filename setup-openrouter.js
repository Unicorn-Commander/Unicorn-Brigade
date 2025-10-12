#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const crypto = require('crypto');
const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

function question(query) {
  return new Promise(resolve => rl.question(query, resolve));
}

function encrypt(text, key) {
  const algorithm = 'aes-256-gcm';
  const salt = crypto.randomBytes(16);
  const derivedKey = crypto.scryptSync(key, salt, 32);
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv(algorithm, derivedKey, iv);

  let encrypted = cipher.update(text, 'utf8', 'hex');
  encrypted += cipher.final('hex');

  const authTag = cipher.getAuthTag();

  return salt.toString('hex') + ':' + iv.toString('hex') + ':' + authTag.toString('hex') + ':' + encrypted;
}

async function setupOpenRouter() {
  console.log('\n🦄 Unicorn Command & Control - OpenRouter Setup\n');
  console.log('This will configure OpenRouter for real AI responses.\n');

  const apiKey = await question('Enter your OpenRouter API key (sk-or-v1-000000000000000000000000000000000000): ');

  if (!apiKey || !apiKey.startsWith('sk-or-')) {
    console.log('❌ Invalid API key format. OpenRouter keys start with "sk-or-"');
    process.exit(1);
  }

  const choice = await question('\nConfigure via:\n1. Database (recommended for production)\n2. .env file (quick testing)\n\nChoice (1 or 2): ');

  if (choice === '1') {
    // Database configuration
    console.log('\n📦 Configuring in database...');

    // Get or generate encryption key
    let encryptionKey = process.env.ENCRYPTION_KEY;
    if (!encryptionKey || encryptionKey === '32-character-encryption-key-here') {
      encryptionKey = crypto.randomBytes(16).toString('hex');
      console.log('\n🔐 Generated new encryption key. Saving to .env...');

      // Update .env file
      const envPath = path.join(__dirname, '.env');
      let envContent = fs.readFileSync(envPath, 'utf8');
      envContent = envContent.replace(/ENCRYPTION_KEY=.*/, `ENCRYPTION_KEY=${encryptionKey}`);
      fs.writeFileSync(envPath, envContent);
    }

    try {
      // Encrypt the API key
      const encryptedKey = encrypt(apiKey, encryptionKey);

      // Check if OpenRouter provider already exists
      const existingProvider = await prisma.aIProvider.findFirst({
        where: { type: 'openrouter' }
      });

      if (existingProvider) {
        // Update existing
        await prisma.aIProvider.update({
          where: { id: existingProvider.id },
          data: {
            apiKey: encryptedKey,
            isActive: true,
            config: JSON.stringify({
              siteName: 'Unicorn Command Control',
              siteUrl: 'http://localhost:8113'
            })
          }
        });
        console.log('✅ Updated existing OpenRouter provider in database');
      } else {
        // Create new
        await prisma.aIProvider.create({
          data: {
            name: 'OpenRouter Primary',
            type: 'openrouter',
            apiKey: encryptedKey,
            endpoint: 'https://openrouter.ai/api/v1',
            isActive: true,
            config: JSON.stringify({
              siteName: 'Unicorn Command Control',
              siteUrl: 'http://localhost:8113'
            })
          }
        });
        console.log('✅ Created OpenRouter provider in database');
      }

      // Deactivate other providers
      await prisma.aIProvider.updateMany({
        where: { type: { not: 'openrouter' } },
        data: { isActive: false }
      });

      console.log('✅ OpenRouter set as active provider');

    } catch (error) {
      console.error('❌ Database error:', error.message);
      process.exit(1);
    }

  } else if (choice === '2') {
    // .env file configuration
    console.log('\n📝 Configuring in .env file...');

    const envPath = path.join(__dirname, '.env');
    let envContent = fs.readFileSync(envPath, 'utf8');

    // Update the OPENROUTER_API_KEY line
    envContent = envContent.replace(/OPENROUTER_API_KEY=.*/, `OPENROUTER_API_KEY=${apiKey}`);

    fs.writeFileSync(envPath, envContent);
    console.log('✅ Updated .env file with OpenRouter API key');

  } else {
    console.log('❌ Invalid choice');
    process.exit(1);
  }

  console.log('\n🎉 OpenRouter configuration complete!');
  console.log('\n🔄 Please restart the server for changes to take effect:');
  console.log('   Press Ctrl+C to stop the server');
  console.log('   Then run: node index.js\n');
  console.log('💬 You can now chat with Dr. Glitter Mane with real AI responses!\n');

  rl.close();
  process.exit(0);
}

setupOpenRouter().catch(error => {
  console.error('❌ Setup failed:', error);
  process.exit(1);
});