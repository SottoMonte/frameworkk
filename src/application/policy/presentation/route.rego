package presentation.route

routes = [
  {"path": "/api/login", "method": "POST", "type": "login"},
  {"path": "/api/logout", "method": "POST", "type": "logout"},
  {"path": "/api/", "method": "GET", "type": "view", "view": "application/view/page/crm/overview.xml"},
  {"path": "/api/github/callback", "method": "GET", "type": "login"},
  {"path": "/api/gather", "method": "GET", "type": "action", "policy": ""},
  {"path": "/api/create", "method": "POST", "type": "action", "policy": ""},
  {"path": "/api/chat", "method": "POST", "type": "action", "policy": ""}
]

default allow = false

allow {
  some r
  r := routes[_]
  input.path == r.path
  input.method == r.method
}