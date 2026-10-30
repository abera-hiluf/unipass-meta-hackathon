/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0b1f3a',
        mist: '#f5f8fc',
        signal: '#2f7df6',
        mint: '#dff7ef',
      },
      boxShadow: { soft: '0 18px 50px rgba(11, 31, 58, 0.08)' },
    },
  },
  plugins: [],
}
