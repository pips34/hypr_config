return {
    {
        "bjarneo/aether.nvim",
        name = "aether",
        priority = 1000,
        opts = {
            disable_italics = false,
            colors = {
                -- Monotone shades (base00-base07)
                base00 = "#171214", -- Default background
                base01 = "#9d7b8b", -- Lighter background (status bars)
                base02 = "#171214", -- Selection background
                base03 = "#9d7b8b", -- Comments, invisibles
                base04 = "#f1f4f2", -- Dark foreground
                base05 = "#f4f1f1", -- Default foreground
                base06 = "#f4f1f1", -- Light foreground
                base07 = "#f1f4f2", -- Light background

                -- Accent colors (base08-base0F)
                base08 = "#ef2a40", -- Variables, errors, red
                base09 = "#f86d7e", -- Integers, constants, orange
                base0A = "#ec7994", -- Classes, types, yellow
                base0B = "#51e65f", -- Strings, green
                base0C = "#76eaef", -- Support, regex, cyan
                base0D = "#6c8eea", -- Functions, keywords, blue
                base0E = "#ec79c3", -- Keywords, storage, magenta
                base0F = "#ec7992", -- Deprecated, brown/yellow
            },
        },
        config = function(_, opts)
            require("aether").setup(opts)
            vim.cmd.colorscheme("aether")

            -- Enable hot reload
            require("aether.hotreload").setup()
        end,
    },
    {
        "LazyVim/LazyVim",
        opts = {
            colorscheme = "aether",
        },
    },
}
