import os
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D
import random

# ---------- DATABASE SETUP ----------
def init_db():
    conn = sqlite3.connect("graph_data.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source INTEGER,
                    target INTEGER
                )''')
    conn.commit()
    conn.close()

# ---------- BACKEND HELPERS ----------
def save_edge(u, v):
    conn = sqlite3.connect("graph_data.db")
    c = conn.cursor()
    c.execute("INSERT INTO edges (source, target) VALUES (?, ?)", (u, v))
    conn.commit()
    conn.close()

def delete_edge(u, v):
    conn = sqlite3.connect("graph_data.db")
    c = conn.cursor()
    c.execute("DELETE FROM edges WHERE (source=? AND target=?) OR (source=? AND target=?)", (u, v, v, u))
    conn.commit()
    conn.close()

def load_edges():
    conn = sqlite3.connect("graph_data.db")
    c = conn.cursor()
    c.execute("SELECT source, target FROM edges")
    edges = c.fetchall()
    conn.close()
    return edges

# ---------- MAIN APPLICATION ----------
class GraphApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Interactive Handshaking Lemma Visualizer")
        # Start with a large, resizable window and dark background
        self.root.geometry("1300x800")
        self.root.minsize(1000, 650)
        self.root.config(bg="#0b0b15")

        # Graph model
        self.G = nx.Graph()
        self.next_node_id = 1

        # UI state
        self.src_var = tk.StringVar()
        self.tgt_var = tk.StringVar()

        self.setup_ui()

        # Load persisted edges from DB and refresh UI
        self.load_from_db()
        self.refresh_graph()

    # ---------- UI SETUP ----------
    def setup_ui(self):
        title = tk.Label(self.root, text="🧮 Handshaking Lemma Visualizer",
                         font=("Helvetica", 22, "bold"), bg="#0b0b15", fg="#00ffff")
        title.pack(pady=8)

        ttk.Style().configure("TButton", font=("Arial", 11, "bold"), padding=6)

        # Top controls frame
        controls = tk.Frame(self.root, bg="#0b0b15")
        controls.pack(fill=tk.X, padx=12, pady=6)

        left_controls = tk.Frame(controls, bg="#0b0b15")
        left_controls.pack(side=tk.LEFT, anchor=tk.N)

        tk.Button(left_controls, text="➕ Add Node", bg="#1e1e2e", fg="white",
                  command=self.add_node).grid(row=0, column=0, padx=6, pady=4)

        # Manual edge creation using text fields (user types node ids)
        node_select_frame = tk.Frame(left_controls, bg="#0b0b15")
        node_select_frame.grid(row=0, column=1, padx=8)
        tk.Label(node_select_frame, text="From:", bg="#0b0b15", fg="#cfefff").grid(row=0, column=0)
        self.src_entry = tk.Entry(node_select_frame, textvariable=self.src_var, width=8, bg="#ffffff")
        self.src_entry.grid(row=0, column=1, padx=4)
        tk.Label(node_select_frame, text="To:", bg="#0b0b15", fg="#cfefff").grid(row=0, column=2)
        self.tgt_entry = tk.Entry(node_select_frame, textvariable=self.tgt_var, width=8, bg="#ffffff")
        self.tgt_entry.grid(row=0, column=3, padx=4)
        tk.Button(node_select_frame, text="🔗 Add Edge", bg="#007acc", fg="white",
                  command=self.add_edge_from_select).grid(row=0, column=4, padx=6)
        # Node list display to help user know available node ids
        self.nodes_display = tk.Label(left_controls, text="Nodes: []", bg="#0b0b15", fg="#cfefff")
        self.nodes_display.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4,0))

        # Edge removal via listbox and utility buttons
        right_controls = tk.Frame(controls, bg="#0b0b15")
        right_controls.pack(side=tk.RIGHT, anchor=tk.N)
        tk.Button(right_controls, text="🌀 Euler Path", bg="#ffcc00", fg="black",
                  command=self.euler_path_check).grid(row=0, column=0, padx=6)
        tk.Button(right_controls, text="💾 Save Graph", bg="#00aaff", fg="white",
                  command=self.save_graph).grid(row=0, column=1, padx=6)
        tk.Button(right_controls, text="🔄 Reset / Refresh", bg="#6a5acd", fg="white",
                  command=self.reset_graph).grid(row=0, column=2, padx=6)

        # Middle area: canvas and side panels
        middle = tk.Frame(self.root, bg="#0b0b15")
        middle.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        # Left: matplotlib canvas
        canvas_frame = tk.Frame(middle, bg="#0b0b15")
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Larger figure with 3 subplots: 2D graph, 3D interactive view, degree histogram
        self.fig = plt.figure(figsize=(15, 6), dpi=100)
        self.ax1 = self.fig.add_subplot(1, 3, 1)
        # 3D axis in the middle
        self.ax3 = self.fig.add_subplot(1, 3, 2, projection='3d')
        self.ax2 = self.fig.add_subplot(1, 3, 3)
        self.fig.patch.set_facecolor("#0b0b15")
        self.ax1.set_facecolor("#0b0b15")
        self.ax2.set_facecolor("#0b0b15")
        self.ax3.set_facecolor("#0b0b15")
        self.ax1.axis("off")

        self.canvas = FigureCanvasTkAgg(self.fig, master=canvas_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        # Bind mouse motion to rotate 3D view
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)

        # Right: edge list, verification panel and log
        right_panel = tk.Frame(middle, width=340, bg="#0b0b15")
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(8,0))

        # Edge listbox
        tk.Label(right_panel, text="Edges", bg="#0b0b15", fg="#cfefff", font=("Arial", 12, "bold")).pack(pady=(6,2))
        self.edge_list = tk.Listbox(right_panel, height=8, bg="#101018", fg="#bfffdc", font=("Consolas", 11), selectbackground="#3333aa")
        self.edge_list.pack(fill=tk.X, padx=6)
        tk.Button(right_panel, text="❌ Remove Selected Edge", bg="#d9534f", fg="white",
                  command=self.remove_selected_edge).pack(pady=6, padx=6)

        # Verification panel
        ver_frame = tk.Frame(right_panel, bg="#0b0b15")
        ver_frame.pack(fill=tk.X, pady=6, padx=6)
        tk.Label(ver_frame, text="Handshaking Lemma", bg="#0b0b15", fg="#ffd966", font=("Arial", 12, "bold")).pack()
        self.deg_label = tk.Label(ver_frame, text="Degrees: []", bg="#0b0b15", fg="#cfefff", anchor="w", justify=tk.LEFT, wraplength=300)
        self.deg_label.pack(fill=tk.X)
        self.sum_label = tk.Label(ver_frame, text="Σ(deg) = 0", bg="#0b0b15", fg="#cfefff")
        self.sum_label.pack(fill=tk.X)
        self.twice_label = tk.Label(ver_frame, text="2×|E| = 0", bg="#0b0b15", fg="#cfefff")
        self.twice_label.pack(fill=tk.X)
        self.result_label = tk.Label(ver_frame, text="Status: —", bg="#0b0b15", fg="#ffffff", font=("Arial", 11, "bold"))
        self.result_label.pack(fill=tk.X, pady=4)
        tk.Button(ver_frame, text="🔍 Verify Now", bg="#00ff99", fg="black", command=self.verify_lemma).pack(pady=2)

        # Logger
        tk.Label(right_panel, text="Activity Log", bg="#0b0b15", fg="#cfefff", font=("Arial", 11, "bold")).pack(pady=(10,2))
        self.log_box = tk.Text(right_panel, height=8, width=40, bg="#0b0b15", fg="#00ffcc", font=("Consolas", 10))
        self.log_box.pack(fill=tk.X, padx=6, pady=(0,8))

        # Initial style updates
        self.update_node_selectors()

    # ---------- GRAPH OPERATIONS ----------
    def add_node(self):
        node_id = self.next_node_id
        self.G.add_node(node_id)
        self.next_node_id = max(self.next_node_id, node_id + 1)
        self.log(f"🟢 Added Node {node_id}")
        self.update_node_selectors()
        self.refresh_graph()

    def add_edge(self):
        # Keep old random behavior as fallback
        nodes = list(self.G.nodes)
        if len(nodes) < 2:
            messagebox.showerror("Error", "Need at least 2 nodes.")
            return
        u, v = random.sample(nodes, 2)
        if self.G.has_edge(u, v):
            messagebox.showinfo("Info", f"Edge {u}-{v} already exists.")
            return
        # Animate edge joining before finalizing
        self.animate_edge(u, v, on_complete=lambda: self._finalize_add_edge(u, v))

    def add_edge_from_select(self):
        try:
            u = int(self.src_var.get())
            v = int(self.tgt_var.get())
        except Exception:
            messagebox.showerror("Error", "Please select two nodes.")
            return
        if u == v:
            messagebox.showerror("Error", "Cannot connect a node to itself.")
            return
        if self.G.has_edge(u, v):
            messagebox.showinfo("Info", f"Edge {u}-{v} already exists.")
            return
        # Animate edge joining before finalizing
        self.animate_edge(u, v, on_complete=lambda: self._finalize_add_edge(u, v))

    def _finalize_add_edge(self, u, v):
        # actually add edge to graph and persist
        if not self.G.has_edge(u, v):
            self.G.add_edge(u, v)
            save_edge(u, v)
            self.log(f"🔗 Added Edge {u}-{v} (saved in DB)")
        self.update_node_selectors()
        self.refresh_graph()

    def animate_edge(self, u, v, duration=700, steps=20, on_complete=None):
        """Animate an edge visually joining between nodes u and v.

        This draws a temporary animated line on ax1 (2D) and ax3 (3D if nodes present),
        then calls on_complete callback after animation finishes.
        duration in milliseconds.
        """
        try:
            # prepare positions
            pos = nx.spring_layout(self.G, seed=42)
            if u not in pos or v not in pos:
                # fallback: refresh to compute positions then try again
                pos = nx.spring_layout(self.G, seed=42)
        except Exception:
            pos = {}

        # 2D positions
        p_u = pos.get(u, (0.0, 0.0))
        p_v = pos.get(v, (0.0, 0.0))

        # For 3D, approximate z as in refresh_graph
        def z_of(p):
            return (p[0] * p[1]) * 0.2

        z_u = z_of(p_u)
        z_v = z_of(p_v)

        # create a Line2D and a 3D line (if needed)
        animated_lines = []

        # Choose a colorful palette that transitions
        cmap = plt.cm.viridis

        # helper to interpolate
        def lerp(a, b, t):
            return a + (b - a) * t

        total = max(1, int(steps))
        interval = max(1, int(duration // total))

        step = {'i': 0}

        # store original axes elements to redraw later
        orig_nodes = None

        def draw_step():
            t = (step['i'] + 1) / total
            # compute intermediate point
            xi = lerp(p_u[0], p_v[0], t)
            yi = lerp(p_u[1], p_v[1], t)

            # color changes with t
            col = cmap(t)

            # draw on ax1: a line from u to intermediate point
            # clear only the temporary lines (we'll remove previous animated lines)
            for ln in animated_lines:
                try:
                    ln.remove()
                except Exception:
                    pass
            animated_lines.clear()

            # Draw partial line in 2D
            l2d, = self.ax1.plot([p_u[0], xi], [p_u[1], yi], color=col, linewidth=3, alpha=0.9)
            animated_lines.append(l2d)

            # Draw partial line in 3D if axis has been set up
            try:
                l3d, = self.ax3.plot([p_u[0], xi], [p_u[1], yi], [z_u, lerp(z_u, z_v, t)], color=col, linewidth=2, alpha=0.9)
                animated_lines.append(l3d)
            except Exception:
                pass

            self.canvas.draw_idle()

            step['i'] += 1
            if step['i'] < total:
                # schedule next frame
                self.root.after(interval, draw_step)
            else:
                # final cleanup of animated lines
                for ln in animated_lines:
                    try:
                        ln.remove()
                    except Exception:
                        pass
                self.canvas.draw_idle()
                if on_complete:
                    on_complete()

        # kick off animation
        draw_step()

    def on_mouse_move(self, event):
        # Rotate 3D view based on mouse x position over the canvas
        if event.x is None or event.y is None:
            return
        bbox = self.canvas.get_tk_widget().bbox()
        try:
            width = bbox[2]
        except Exception:
            width = self.canvas.get_tk_widget().winfo_width()
        if width <= 0:
            return
        rel = max(0.0, min(1.0, event.x / width))
        azim = 360 * rel
        self.ax3.view_init(elev=30, azim=azim)
        self.canvas.draw_idle()

    def remove_edge(self):
        # Legacy random removal retained; prefer using remove_selected_edge
        if not self.G.edges:
            messagebox.showerror("Error", "No edges to remove.")
            return
        u, v = random.choice(list(self.G.edges))
        self.G.remove_edge(u, v)
        delete_edge(u, v)
        self.log(f"❌ Removed Edge {u}-{v} (removed from DB)")
        self.update_node_selectors()
        self.refresh_graph()

    def remove_selected_edge(self):
        sel = self.edge_list.curselection()
        if not sel:
            messagebox.showerror("Error", "Select an edge to remove.")
            return
        item = self.edge_list.get(sel[0])
        parts = item.split("-")
        try:
            u = int(parts[0].strip())
            v = int(parts[1].strip())
        except Exception:
            messagebox.showerror("Error", "Failed to parse selected edge.")
            return
        if self.G.has_edge(u, v):
            self.G.remove_edge(u, v)
        delete_edge(u, v)
        self.log(f"❌ Removed Edge {u}-{v} (removed from DB)")
        self.update_node_selectors()
        self.refresh_graph()

    def verify_lemma(self):
        degrees = [deg for _, deg in self.G.degree()]
        degree_sum = sum(degrees)
        edge_twice = 2 * self.G.number_of_edges()

        # Update visible verification panel
        self.deg_label.config(text=f"Degrees: {degrees}")
        self.sum_label.config(text=f"Σ(deg) = {degree_sum}")
        self.twice_label.config(text=f"2×|E| = {edge_twice}")

        if degree_sum == edge_twice:
            self.result_label.config(text="Status: ✅ Handshaking Lemma Verified!", fg="#7CFC00")
            self.log("✅ Handshaking Lemma Verified!")
        else:
            self.result_label.config(text=f"Status: ❌ Mismatch", fg="#ff6666")
            self.log("❌ Handshaking Lemma Failed!")

        self.refresh_graph(highlight_odd=True)

    def euler_path_check(self):
        odd_degree_nodes = [n for n, d in self.G.degree() if d % 2 != 0]
        if len(odd_degree_nodes) == 0:
            self.log("🔵 Euler Circuit exists (all degrees even).")
        elif len(odd_degree_nodes) == 2:
            self.log("🟣 Euler Path exists (two odd-degree vertices).")
        else:
            self.log(f"🔴 No Euler Path/Circuit (odd-degree count: {len(odd_degree_nodes)})")
        self.refresh_graph()

    def save_graph(self):
        nx.write_gpickle(self.G, "graph_data.gpickle")
        self.log("💾 Graph saved successfully!")

    def load_from_db(self):
        # Load edges from sqlite DB and construct graph
        edges = load_edges()
        nodes = set()
        for u, v in edges:
            try:
                uu = int(u)
                vv = int(v)
            except Exception:
                continue
            self.G.add_edge(uu, vv)
            nodes.add(uu)
            nodes.add(vv)
        if nodes:
            self.next_node_id = max(nodes) + 1
        else:
            # start fresh
            self.next_node_id = 1
        self.update_node_selectors()
        self.log(f"📥 Loaded {self.G.number_of_edges()} edges from DB")

    # ---------- GRAPH RENDER ----------
    def refresh_graph(self, highlight_odd=False):

        self.ax1.clear()
        pos = nx.spring_layout(self.G, seed=42)
        # Use a deterministic, sorted node order so UI displays match node ids
        nodes = sorted(list(self.G.nodes()))
        degrees = {n: self.G.degree(n) for n in nodes}

        # Node colors via colormap according to degree
        # Node colors via colormap according to degree, aligned with sorted nodes
        deg_vals = [degrees.get(n, 0) for n in nodes]
        if deg_vals:
            maxdeg = max(deg_vals) if max(deg_vals) > 0 else 1
        else:
            maxdeg = 1

        cmap = plt.cm.plasma
        node_colors = [cmap(d / maxdeg) for d in deg_vals]
        edge_color = "#74f7ff"

        # draw nodes/edges using the same 'pos' but ensure nodes are plotted in sorted order
        nx.draw_networkx_edges(self.G, pos, ax=self.ax1, edge_color=edge_color, alpha=0.9)
        nx.draw_networkx_nodes(self.G, pos, nodelist=nodes, ax=self.ax1, node_color=node_colors, node_size=900, linewidths=1.2, edgecolors="#0b0b15")
        nx.draw_networkx_labels(self.G, pos, labels={n: str(n) for n in nodes}, ax=self.ax1, font_color="white")

        self.ax1.set_title("Graph View", color="#cfefff")
        self.ax1.axis('off')

        # 3D view: place nodes on a sphere for a pleasant 3D layout
        self.ax3.clear()
        n = len(self.G.nodes())
        if n > 0:
            # keep consistent node ordering here as well
            nodes = sorted(list(self.G.nodes()))
            # use spring_layout to get 2D coords then lift into 3D
            pos2d = nx.spring_layout(self.G, seed=42)
            xs = []
            ys = []
            zs = []
            for i, node in enumerate(nodes):
                x2, y2 = pos2d.get(node, (0, 0))
                # map 2D to 3D by adding a z component as small function
                xs.append(x2)
                ys.append(y2)
                zs.append((x2 * y2) * 0.2)
            # colors from the same colormap (aligned to sorted nodes)
            deg_vals = [self.G.degree(n) for n in nodes]
            maxdeg = max(deg_vals) if deg_vals and max(deg_vals) > 0 else 1
            cmap = plt.cm.plasma
            node_colors_3d = [cmap(d / maxdeg) for d in deg_vals]
            self.ax3.scatter(xs, ys, zs, s=140, c=node_colors_3d, depthshade=True, edgecolors='k')
            # draw simple 3D edges
            for u, v in self.G.edges():
                try:
                    iu = nodes.index(u)
                    iv = nodes.index(v)
                except ValueError:
                    continue
                self.ax3.plot([xs[iu], xs[iv]], [ys[iu], ys[iv]], [zs[iu], zs[iv]], color='#74f7ff', alpha=0.6)
        self.ax3.set_title('3D View (move mouse to rotate)', color='#cfefff')
        self.ax3.set_xticks([])
        self.ax3.set_yticks([])
        self.ax3.set_zticks([])

        # Degree histogram (x-axis labelled with actual node ids)
        self.ax2.clear()
        deg_values = [degrees.get(n, 0) for n in nodes]
        if nodes:
            self.ax2.bar(range(len(deg_values)), deg_values, color="#00ffcc", edgecolor="#0b3f3f")
            # label ticks with node ids instead of 0..n-1
            self.ax2.set_xticks(range(len(nodes)))
            self.ax2.set_xticklabels([str(n) for n in nodes], color='white')
        else:
            self.ax2.bar([], [])
        self.ax2.set_title("Degree Distribution", color="white")
        self.ax2.tick_params(colors="white")

        # Update edge listbox
        self.edge_list.delete(0, tk.END)
        for u, v in sorted(self.G.edges()):
            self.edge_list.insert(tk.END, f"{u} - {v}")

        # Update nodes display label
        self.nodes_display.config(text=f"Nodes: {nodes}")

        self.canvas.draw()

    def reset_graph(self):
        # Clear DB table and gpickle if present, then reset in-memory graph
        conn = sqlite3.connect("graph_data.db")
        c = conn.cursor()
        c.execute("DELETE FROM edges")
        conn.commit()
        conn.close()

        # remove gpickle if exists
        try:
            if os.path.exists("graph_data.gpickle"):
                os.remove("graph_data.gpickle")
        except Exception:
            pass

        # Reset in-memory graph
        self.G.clear()
        self.next_node_id = 1
        self.update_node_selectors()
        self.log("🔄 Graph and DB reset. Start from scratch.")
        # Reset verification panel
        self.deg_label.config(text="Degrees: []")
        self.sum_label.config(text="Σ(deg) = 0")
        self.twice_label.config(text="2×|E| = 0")
        self.result_label.config(text="Status: —", fg="#ffffff")
        self.refresh_graph()

    # ---------- LOGGER ----------
    def log(self, message):
        self.log_box.insert(tk.END, f"{message}\n")
        self.log_box.see(tk.END)

    def update_node_selectors(self):
        nodes = sorted(list(self.G.nodes()))
        if not nodes:
            nodes = []
        # Update the nodes display label and clear entry boxes if empty
        self.nodes_display.config(text=f"Nodes: {nodes}")
        if not nodes:
            self.src_var.set("")
            self.tgt_var.set("")


# ---------- RUN APP ----------
if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    app = GraphApp(root)
    root.mainloop()
