from typing import List
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os

from database import get_db, init_db, create_sample_data


# Pydantic models
class ItemBase(BaseModel):
    name: str
    quantity: int = 1
    completed: bool = False


class ItemCreate(ItemBase):
    pass


class Item(ItemBase):
    id: int

    class Config:
        from_attributes = True


# Initialize FastAPI app
app = FastAPI(
    title="Shared Shopping List API",
    description="A simple shopping list API with SQLite backend",
    version="1.0.0",
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates (for potential future use)
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def startup_event():
    """Initialize database on startup"""
    init_db()
    create_sample_data()


@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    """Serve the PWA frontend"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api", response_model=dict)
async def api_info():
    """API information endpoint for testing"""
    return {"message": "Shared Shopping List API"}


@app.get("/items", response_model=List[Item])
async def get_items():
    """Get all shopping items"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, name, quantity, completed FROM items ORDER BY id"
        )
        items = [dict(row) for row in cursor.fetchall()]
        return items


@app.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: int):
    """Get a specific shopping item by ID"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, name, quantity, completed FROM items WHERE id = ?", (item_id,)
        )
        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Item not found")

        return dict(row)


@app.post("/items", response_model=Item, status_code=201)
async def create_item(item: ItemCreate):
    """Create a new shopping item"""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO items (name, quantity, completed) VALUES (?, ?, ?)",
            (item.name, item.quantity, item.completed),
        )
        conn.commit()

        # Get the created item
        new_id = cursor.lastrowid
        cursor = conn.execute(
            "SELECT id, name, quantity, completed FROM items WHERE id = ?", (new_id,)
        )
        new_item = cursor.fetchone()

        return dict(new_item)


@app.put("/items/{item_id}", response_model=Item)
async def update_item(item_id: int, item: ItemCreate):
    """Update an existing shopping item"""
    with get_db() as conn:
        # Check if item exists
        cursor = conn.execute("SELECT id FROM items WHERE id = ?", (item_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Item not found")

        # Update the item
        conn.execute(
            "UPDATE items SET name = ?, quantity = ?, completed = ? WHERE id = ?",
            (item.name, item.quantity, item.completed, item_id),
        )
        conn.commit()

        # Return the updated item
        cursor = conn.execute(
            "SELECT id, name, quantity, completed FROM items WHERE id = ?", (item_id,)
        )
        updated_item = cursor.fetchone()

        return dict(updated_item)


@app.delete("/items/{item_id}")
async def delete_item(item_id: int):
    """Delete a shopping item"""
    with get_db() as conn:
        # Check if item exists
        cursor = conn.execute("SELECT id FROM items WHERE id = ?", (item_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Item not found")

        # Delete the item
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()

        return {"message": "Item deleted successfully"}


@app.patch("/items/{item_id}/toggle")
async def toggle_item(item_id: int):
    """Toggle the completed status of an item"""
    with get_db() as conn:
        # Check if item exists
        cursor = conn.execute(
            "SELECT id, completed FROM items WHERE id = ?", (item_id,)
        )
        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Item not found")

        # Toggle the completed status
        new_status = not bool(row["completed"])
        conn.execute(
            "UPDATE items SET completed = ? WHERE id = ?", (new_status, item_id)
        )
        conn.commit()

        return {"id": item_id, "completed": new_status}


@app.delete("/items")
async def clear_items():
    """Clear all items from the shopping list"""
    with get_db() as conn:
        conn.execute("DELETE FROM items")
        conn.commit()

        return {"message": "All items cleared successfully"}


@app.get("/static/sw.js")
async def get_service_worker():
    """Serve the service worker with proper headers"""
    response = FileResponse("app/static/sw.js")
    response.headers["Service-Worker-Allowed"] = "/"
    return response


if __name__ == "__main__":
    import uvicorn

    # Get host and port from environment variables or use defaults
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))

    print(f"Starting server on {host}:{port}")
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
