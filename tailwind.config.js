/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./StudentProfiles/templates/**/*.html",
    "./TeacherPortal/templates/**/*.html",
    "./dashboard/templates/**/*.html",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#e3125b',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
    require('@tailwindcss/aspect-ratio'),
  ],
} 