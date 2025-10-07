#!/usr/bin/env python3
"""
Simplified entry point for SottoMonte Framework
This bypasses the complex module loading system and directly starts the Starlette server
"""

import sys
import os
import asyncio

# Add src to path
cwd = os.getcwd()
sys.path.insert(1, cwd + '/src')

# Import required modules directly
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import uvicorn


# Simple middleware for no-cache headers
class NoCacheMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.extend([
                        (b"cache-control", b"no-store, no-cache, must-revalidate"),
                        (b"pragma", b"no-cache"),
                        (b"expires", b"0"),
                        (b"server", b"SottoMonte-Simplified")
                    ])
                    message["headers"] = headers
                await send(message)
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)


async def homepage(request):
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SottoMonte Framework</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    </head>
    <body>
        <div class="container mt-5">
            <div class="row justify-content-center">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-body text-center">
                            <h1 class="card-title text-primary">
                                <i class="bi bi-server"></i> SottoMonte Framework
                            </h1>
                            <p class="card-text">
                                Web application is running successfully on Replit!
                            </p>
                            <div class="alert alert-success" role="alert">
                                <i class="bi bi-check-circle"></i> Server is running on port 5000
                            </div>
                            <div class="row mt-4">
                                <div class="col-md-6">
                                    <div class="card bg-light">
                                        <div class="card-body">
                                            <h5 class="card-title">
                                                <i class="bi bi-gear"></i> Configuration
                                            </h5>
                                            <p class="card-text">
                                                Host: 0.0.0.0:5000<br>
                                                Framework: Starlette<br>
                                                Environment: Replit
                                            </p>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="card bg-light">
                                        <div class="card-body">
                                            <h5 class="card-title">
                                                <i class="bi bi-info-circle"></i> Status
                                            </h5>
                                            <p class="card-text">
                                                Application: Ready<br>
                                                CORS: Enabled<br>
                                                Cache: Disabled
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


def create_app():
    """Create and configure the Starlette application"""
    
    # Define routes
    routes = [
        Route("/", homepage),
    ]
    
    # Define middleware
    middleware = [
        Middleware(SessionMiddleware, secret_key="replit-sottomonte-demo-key"),
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True),
        Middleware(NoCacheMiddleware),
    ]
    
    # Create application
    app = Starlette(debug=True, routes=routes, middleware=middleware)
    
    return app


def main():
    """Main entry point"""
    print("🚀 Starting SottoMonte Framework (Simplified Mode)")
    print("📡 Binding to 0.0.0.0:5000")
    print("🌐 CORS enabled for all origins")
    print("🚫 Caching disabled")
    
    app = create_app()
    
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        reload=False,
        access_log=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()