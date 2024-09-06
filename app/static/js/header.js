var colorMode = "light";

$.ajax({
    url: "/settings/appearance",
    type: "GET",
    async: false,
    success: function (response) {
        console.log(response);
        let colorMode = response.theme;
        if (colorMode === "system") {
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                colorMode = "dark";
            }
            else {
                colorMode = "light";
            }
        }

        let accentColor = response["color-" + colorMode];

        changeColorMode(colorMode, accentColor);
    }
});


function changeColorMode(colorMode, accentColor) {
    var oldLink = document.getElementById("currentCss");

    var newlink = document.createElement("link");
    newlink.setAttribute("rel", "stylesheet");
    newlink.setAttribute("type", "text/css");
    newlink.setAttribute("id", "currentCss");
    console.log(colorMode);

    if (colorMode == "dark") {
        newlink.setAttribute("href", themeLinkDark);
        img = document.getElementById("header-icon");
        img.src = iconLinkDark;
    } else {
        newlink.setAttribute("href", themeLinkLight);
        img = document.getElementById("header-icon");
        img.src = iconLinkLight;
    }

    document.getElementsByTagName("head").item(0).replaceChild(newlink, oldLink);
    


    //check if accentColor is not just ""
    if (accentColor !== "" && accentColor !== null && accentColor !== undefined) {
        console.log("new accent Color: " + accentColor);
        document.documentElement.style.setProperty("--accent-color-interaction", accentColor);
    }

};

function redirectSettingsPage() {
    window.location.href = "/settings";
}