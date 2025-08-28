/* eslint-disable no-undef */
import plugin from 'tailwindcss/plugin';
import defaultTheme from 'tailwindcss/defaultTheme';
import path from 'path';

// Custom styles classes. Added here for type hinting
const plug = plugin(({ addComponents, theme }) => {
  addComponents({
    '.black-btn': {
      // for robocorp design Button works only for variant='ghost'
      backgroundColor: 'black',
      borderRadius: '9999px',
      color: 'white',
      '&:hover': {
        backgroundColor: theme('colors.gray[700]'),
      },
      '&:disabled': {
        backgroundColor: theme('colors.gray[300]'),
        cursor: 'not-allowed',
      },

      // Styles for robocorp Button
      '&>div': {
        color: 'white',
        borderRadius: '9999px',
      },
      overflow: 'hidden',
    },
    '.white-btn': {
      backgroundColor: 'white',
      borderRadius: '9999px',
      color: 'black',
      border: `1px solid ${theme('colors.gray[300]')}`,
      '&:hover': {
        backgroundColor: theme('colors.gray[100]'),
      },
      '&:disabled': {
        backgroundColor: theme('colors.gray[300]'),
        cursor: 'not-allowed',
      },
    },
    '.dark-tooltip': {
      '@apply !bg-[#282833] !px-3 text-xs font-sans': {},
    },
    '.gray-btn': {
      backgroundColor: theme('colors.gray[200]'),
      borderRadius: '9999px',
      color: 'black',
      border: `1px solid ${theme('colors.gray[200]')}`,
      '&:hover': {
        backgroundColor: theme('colors.gray[300]'),
      },
      '&:disabled': {
        backgroundColor: theme('colors.gray[400]'),
        cursor: 'not-allowed',
      },
    },
    '.hide-scrollbar': {
      '-ms-overflow-style': 'none',
      'scrollbar-width': 'none',

      '&::-webkit-scrollbar': {
        display: 'none',
      },
    },
  });
});

/** @type {import('tailwindcss').Config} */

let agentComponentPath = require
  .resolve('@sema4ai/agent-components')
  .replace('dist/index.js', '')
  .replace('dist\\index.js', '');

if (!agentComponentPath.includes('node_modules')) {
  agentComponentPath = path.join(agentComponentPath, 'src');
}

export default {
  content: [
    path.resolve(__dirname, './index.html'),
    path.resolve(__dirname, './src/**/*.{js,ts,jsx,tsx}'),
    `${agentComponentPath}/**/*.{js,ts,jsx,tsx,html,css}`,
  ],
  theme: {
    extend: {
      fontFamily: {
        inter: ['Inter', 'Mona Sans', ...defaultTheme.fontFamily.sans],
        sans: ['Mona Sans', ...defaultTheme.fontFamily.sans],
        mono: ['DM Mono', ...defaultTheme.fontFamily.mono],
      },
      colors: {
        sema4: '#2E5842',
        sema4Hover: '#2E6147',
        sema4Active: '#274D39',
      },
    },
  },
  plugins: [require('@tailwindcss/typography'), plug],
};
