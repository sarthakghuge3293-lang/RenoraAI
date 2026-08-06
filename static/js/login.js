/* ==========================================
   RENVORA AI LOGIN
   login.js
========================================== */

document.addEventListener("DOMContentLoaded", () => {

    const intro = document.getElementById("intro");
    const logoTop = document.querySelector(".logo-top");
    const password = document.getElementById("password");
    const togglePassword = document.getElementById("togglePassword");
    const form = document.querySelector("form");
    const loginBtn = document.querySelector(".login-btn");

    /* ==========================
       Show / Hide Password
    ========================== */

    if (togglePassword && password) {

        togglePassword.addEventListener("click", () => {

            const type =
                password.type === "password"
                ? "text"
                : "password";

            password.type = type;

            togglePassword.innerHTML =
                type === "password"
                ? '<i class="fa-solid fa-eye"></i>'
                : '<i class="fa-solid fa-eye-slash"></i>';

        });

    }

    /* ==========================
       Login Button Loading
    ========================== */

    if (form && loginBtn) {

        form.addEventListener("submit", () => {

            loginBtn.disabled = true;

            loginBtn.innerHTML =
            '<i class="fa-solid fa-spinner fa-spin"></i> Signing In...';

        });

    }

    /* ==========================
       Intro Animation
    ========================== */

    setTimeout(() => {

        if (intro) {

            intro.style.transition = "all .8s ease";
            intro.style.opacity = "0";

            setTimeout(() => {

                intro.style.display = "none";

                document.body.classList.add("loaded");

            },800);

        }

    },3000);

    /* ==========================
       Logo Float
    ========================== */

    if (logoTop) {

        setInterval(() => {

            logoTop.animate(

                [

                    {
                        transform:"translateY(0px)"
                    },

                    {
                        transform:"translateY(-8px)"
                    },

                    {
                        transform:"translateY(0px)"
                    }

                ],

                {

                    duration:2500

                }

            );

        },2500);

    }

});