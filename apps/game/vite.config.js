import {defineConfig} from 'vite';
export default defineConfig({server:{port:5173,strictPort:true,proxy:{
 '/api/game':{target:'http://127.0.0.1:8016',changeOrigin:false},
}}});
