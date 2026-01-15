from typing import List, AsyncGenerator
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os
import asyncio
import json
import tomllib
from datetime import datetime
from contextlib import asynccontextmanager

from database import get_db, init_db, create_sample_data


def get_app_version() -> str:
    """Read the app version from pyproject.toml"""
    try:
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]
    except (FileNotFoundError, KeyError):
        # Fallback to a default version if pyproject.toml is not found or malformed
        return "0.0.0"


# Event broadcasting system
class EventBroadcaster:
    def __init__(self):
        self.listeners: List[asyncio.Queue] = []

    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to events and return a queue"""
        queue = asyncio.Queue()
        self.listeners.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from events"""
        if queue in self.listeners:
            self.listeners.remove(queue)

    async def broadcast(self, event_data: dict):
        """Broadcast event to all listeners"""
        for queue in self.listeners:
            try:
                await queue.put(event_data)
            except Exception:
                # Remove dead listeners
                self.listeners.remove(queue)

    async def shutdown(self):
        """Clean shutdown - close all connections"""
        shutdown_event = {
            "type": "shutdown",
            "message": "Server is shutting down",
            "timestamp": datetime.now().isoformat(),
        }

        # Broadcast shutdown event to all listeners
        await self.broadcast(shutdown_event)

        # Clear all listeners to force SSE connections to close
        self.listeners.clear()


# Global broadcaster instance
broadcaster = EventBroadcaster()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    init_db()
    create_sample_data()
    yield
    # Shutdown - clean up SSE connections
    await broadcaster.shutdown()


# Pydantic models
class ShoppingListBase(BaseModel):
    name: str


class ShoppingListCreate(ShoppingListBase):
    pass


class ShoppingList(ShoppingListBase):
    id: int
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class ItemBase(BaseModel):
    name: str
    quantity: int = 1
    completed: bool = False
    order_index: int = 0


class ItemCreate(ItemBase):
    pass


class Item(ItemBase):
    id: int

    model_config = {"from_attributes": True}


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Shared Shopping List API",
    description="A simple shopping list API with SQLite backend",
    version=get_app_version(),
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates (for potential future use)
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    """Serve the PWA frontend"""
    return templates.TemplateResponse(
        "index.html", {"request": request, "version": get_app_version()}
    )


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
async def update_list(list_id: int, list_data: ShoppingListCreate, request: Request):
    """Update a shopping list's name"""
    client_id = request.headers.get("X-Client-ID")

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

        # Broadcast list update event
        await broadcaster.broadcast(
            {
                "type": "list_update",
                "list_id": list_id,
                "name": list_data.name,
                "client_id": client_id,
                "timestamp": datetime.now().isoformat(),
            }
        )

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
async def create_item(item: ItemCreate, request: Request, list_id: int = 1):
    """Create a new shopping item"""
    client_id = request.headers.get("X-Client-ID")

    with get_db() as conn:
        if item.order_index > 0:
            # Insert at specific position - shift higher order_indices up
            conn.execute(
                "UPDATE items SET order_index = order_index + 1 WHERE list_id = ? AND order_index >= ?",
                (list_id, item.order_index),
            )
            insert_order = item.order_index
        else:
            # Append at the end
            cursor = conn.execute(
                "SELECT COALESCE(MAX(order_index), 0) + 1 FROM items WHERE list_id = ?",
                (list_id,),
            )
            insert_order = cursor.fetchone()[0]

        cursor = conn.execute(
            "INSERT INTO items (list_id, name, quantity, completed, order_index) VALUES (?, ?, ?, ?, ?)",
            (list_id, item.name, item.quantity, item.completed, insert_order),
        )
        conn.commit()

        # Get the created item
        new_id = cursor.lastrowid
        cursor = conn.execute(
            "SELECT id, name, quantity, completed, order_index FROM items WHERE id = ?",
            (new_id,),
        )
        new_item = cursor.fetchone()

        # Broadcast item creation event
        await broadcaster.broadcast(
            {
                "type": "item_created",
                "item": dict(new_item),
                "list_id": list_id,
                "client_id": client_id,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return dict(new_item)


@app.put("/items/{item_id}", response_model=Item)
async def update_item(item_id: int, item: ItemCreate, request: Request):
    """Update an existing shopping item"""
    client_id = request.headers.get("X-Client-ID")

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

        # Broadcast item update event
        await broadcaster.broadcast(
            {
                "type": "item_updated",
                "item": dict(updated_item),
                "client_id": client_id,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return dict(updated_item)


@app.delete("/items/{item_id}")
async def delete_item(item_id: int, request: Request):
    """Delete a shopping item"""
    client_id = request.headers.get("X-Client-ID")

    with get_db() as conn:
        # Check if item exists and get list_id
        cursor = conn.execute("SELECT id, list_id FROM items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Item not found")

        list_id = row["list_id"]

        # Delete the item
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()

        # Broadcast item deletion event
        await broadcaster.broadcast(
            {
                "type": "item_deleted",
                "item_id": item_id,
                "list_id": list_id,
                "client_id": client_id,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return {"message": "Item deleted successfully"}


@app.patch("/items/{item_id}/toggle")
async def toggle_item(item_id: int, request: Request):
    """Toggle the completed status of an item"""
    client_id = request.headers.get("X-Client-ID")

    with get_db() as conn:
        # Check if item exists
        cursor = conn.execute(
            "SELECT id, completed, list_id FROM items WHERE id = ?", (item_id,)
        )
        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Item not found")

        # Toggle the completed status
        new_status = not bool(row["completed"])
        list_id = row["list_id"]
        conn.execute(
            "UPDATE items SET completed = ? WHERE id = ?", (new_status, item_id)
        )
        conn.commit()

        # Broadcast item toggle event
        await broadcaster.broadcast(
            {
                "type": "item_toggled",
                "item_id": item_id,
                "completed": new_status,
                "list_id": list_id,
                "client_id": client_id,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return {"id": item_id, "completed": new_status}


@app.patch("/items/{item_id}/reorder/{new_order}")
async def reorder_item(item_id: int, new_order: int, request: Request):
    """Reorder a shopping item to a new position"""
    client_id = request.headers.get("X-Client-ID")

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

        # Broadcast item reorder event
        await broadcaster.broadcast(
            {
                "type": "item_reordered",
                "item_id": item_id,
                "old_order": current_order,
                "new_order": new_order,
                "list_id": list_id,
                "client_id": client_id,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return {"id": item_id, "order_index": new_order}


@app.delete("/items")
async def clear_items(request: Request, list_id: int = 1):
    """Clear all items from a specific shopping list"""
    client_id = request.headers.get("X-Client-ID")

    with get_db() as conn:
        conn.execute("DELETE FROM items WHERE list_id = ?", (list_id,))
        conn.commit()

        # Broadcast clear event
        await broadcaster.broadcast(
            {
                "type": "clear",
                "list_id": list_id,
                "client_id": client_id,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return {"message": "All items cleared successfully"}


@app.get("/events")
async def events() -> StreamingResponse:
    """Server-Sent Events endpoint for real-time updates"""

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events"""
        # Subscribe to broadcaster
        queue = await broadcaster.subscribe()

        try:
            # Send initial ping to establish connection
            yield f"data: {json.dumps({'type': 'ping', 'timestamp': datetime.now().isoformat()})}\n\n"

            while True:
                try:
                    # Wait for event with timeout
                    event_data = await asyncio.wait_for(queue.get(), timeout=30)

                    # Check for shutdown event
                    if event_data.get("type") == "shutdown":
                        # Send shutdown notification and close connection
                        yield f"data: {json.dumps(event_data)}\n\n"
                        break

                    # Send the event
                    yield f"data: {json.dumps(event_data)}\n\n"

                except asyncio.TimeoutError:
                    # Send keep-alive ping
                    yield f"data: {json.dumps({'type': 'ping', 'timestamp': datetime.now().isoformat()})}\n\n"

        except Exception as e:
            print(f"SSE error: {e}")
        finally:
            # Unsubscribe when done
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        },
    )


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
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
