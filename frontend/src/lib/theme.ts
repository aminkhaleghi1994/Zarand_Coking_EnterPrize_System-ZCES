export const THEME_STORAGE_KEY = "zces-theme";

export const THEME_INIT_SCRIPT = `(function(){try{var e=document.documentElement,t=localStorage.getItem("${THEME_STORAGE_KEY}"),a=t?t==="dark":window.matchMedia("(prefers-color-scheme: dark)").matches;e.classList.toggle("dark",a),e.style.colorScheme=a?"dark":"light",window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change",function(a){localStorage.getItem("${THEME_STORAGE_KEY}")||(e.classList.toggle("dark",a.matches),e.style.colorScheme=a.matches?"dark":"light")})}catch(e){}})();`;
