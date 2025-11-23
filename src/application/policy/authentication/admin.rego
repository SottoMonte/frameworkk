package authentication.admin

can_manage_users {
  input.user.roles[_] == "admin"
}

can_access_admin_panel {
  input.user.roles[_] == "admin"
}