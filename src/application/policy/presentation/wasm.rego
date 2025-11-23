package presentation.wasm

# Feature toggle visibili solo a determinati ruoli
default feature_enabled = false

feature_enabled {
  input.user.roles[_] == "beta-tester"
  input.feature == "new-ui"
}

feature_enabled {
  input.user.roles[_] == "admin"
}

# Controlla accesso a componenti UI dinamici
can_render_component {
  input.component == "DashboardStats"
  input.user.roles[_] in ["admin", "editor"]
}

can_render_component {
  input.component == "PublicInfo"
}