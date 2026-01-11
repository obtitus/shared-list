from typing import List
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os

from database import get_db, init_db, create_sample_data


# Pydantic models
class ShoppingListBase(BaseModel):
    name: str


class ShoppingListCreate(ShoppingListBase):
    pass


class ShoppingList(ShoppingListBase):
    id: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ItemBase(BaseModel):
    name: str
    quantity: int = 1
    completed: bool = False
    order_index: int = 0


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


@app.get("/lists", response_model=List[ShoppingList])
async def get_lists():
    """Get all shopping lists"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, name, created_at, updated_at FROM lists ORDER BY id"
        )
        lists = [dict(row) for row in cursor.fetchall()]
        return lists


@app.get("/lists/{list_id}", response_model=ShoppingList)
async def get_list(list_id: int):
    """Get a specific shopping list by ID"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, name, created_at, updated_at FROM lists WHERE id = ?",
            (list_id,),
        )
        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="List not found")

        return dict(row)


@app.put("/lists/{list_id}", response_model=ShoppingList)
async def update_list(list_id: int, list_data: ShoppingListCreate):
    """Update a shopping list's name"""
    with get_db() as conn:
        # Check if list exists
        cursor = conn.execute("SELECT id FROM lists WHERE id = ?", (list_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="List not found")

        # Update the list
        conn.execute(
            "UPDATE lists SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (list_data.name, list_id),
        )
        conn.commit()

        # Return the updated list
        cursor = conn.execute(
            "SELECT id, name, created_at, updated_at FROM lists WHERE id = ?",
            (list_id,),
        )
        updated_list = cursor.fetchone()

        return dict(updated_list)


@app.get("/items", response_model=List[Item])
async def get_items(list_id: int = 1):
    """Get all shopping items for a specific list"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, name, quantity, completed, order_index FROM items WHERE list_id = ? ORDER BY order_index, id",
            (list_id,),
        )
        items = [dict(row) for row in cursor.fetchall()]
        return items


@app.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: int):
    """Get a specific shopping item by ID"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, name, quantity, completed, order_index FROM items WHERE id = ?",
            (item_id,),
        )
        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Item not found")

        return dict(row)


@app.post("/items", response_model=Item, status_code=201)
async def create_item(item: ItemCreate, list_id: int = 1):
    """Create a new shopping item"""
    with get_db() as conn:
        # Get the next order_index for this list
        cursor = conn.execute(
            "SELECT COALESCE(MAX(order_index), 0) + 1 FROM items WHERE list_id = ?",
            (list_id,),
        )
        next_order = cursor.fetchone()[0]

        cursor = conn.execute(
            "INSERT INTO items (list_id, name, quantity, completed, order_index) VALUES (?, ?, ?, ?, ?)",
            (list_id, item.name, item.quantity, item.completed, next_order),
        )
        conn.commit()

        # Get the created item
        new_id = cursor.lastrowid
        cursor = conn.execute(
            "SELECT id, name, quantity, completed, order_index FROM items WHERE id = ?",
            (new_id,),
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
            "UPDATE items SET name = ?, quantity = ?, completed = ?, order_index = ? WHERE id = ?",
            (item.name, item.quantity, item.completed, item.order_index, item_id),
        )
        conn.commit()

        # Return the updated item
        cursor = conn.execute(
            "SELECT id, name, quantity, completed, order_index FROM items WHERE id = ?",
            (item_id,),
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


@app.patch("/items/{item_id}/reorder")
async def reorder_item(item_id: int, new_order: int = Body(...)):
    """Reorder a shopping item to a new position"""
    with get_db() as conn:
        # Check if item exists and get its list_id
        cursor = conn.execute(
            "SELECT id, order_index, list_id FROM items WHERE id = ?", (item_id,)
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Item not found")

        current_order = row["order_index"]
        list_id = row["list_id"]

        if current_order == new_order:
            return {"message": "Item order unchanged"}

        # Update order indices to make room for the new position (within the same list)
        if new_order > current_order:
            # Moving down - shift items up
            conn.execute(
                "UPDATE items SET order_index = order_index - 1 WHERE list_id = ? AND order_index > ? AND order_index <= ?",
                (list_id, current_order, new_order),
            )
        else:
            # Moving up - shift items down
            conn.execute(
                "UPDATE items SET order_index = order_index + 1 WHERE list_id = ? AND order_index >= ? AND order_index < ?",
                (list_id, new_order, current_order),
            )

        # Update the item's order_index
        conn.execute(
            "UPDATE items SET order_index = ? WHERE id = ?",
            (new_order, item_id),
        )
        conn.commit()

        return {"id": item_id, "order_index": new_order}


@app.delete("/items")
async def clear_items(list_id: int = 1):
    """Clear all items from a specific shopping list"""
    with get_db() as conn:
        conn.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
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
